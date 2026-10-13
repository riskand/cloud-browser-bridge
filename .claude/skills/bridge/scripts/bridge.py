"""Set up, start, stop and check the bridge and its Cloudflare quick tunnel (README Part A).

Standard library only, so it runs before the virtual environment exists:

    python3 .claude/skills/bridge/scripts/bridge.py setup|start|status|stop

Both processes run detached from the caller and outlive it. Pid files and logs go to `.bridge/`,
and so does `browser-bridge.zip`: the cloud-session instructions with the current tunnel address
filled in, to attach to a cloud session. It is rewritten on every start, removed on stop, and never
contains the token.
"""

from __future__ import annotations  # an older system Python reaches pip's version error

import argparse
import contextlib
import os
import re
import secrets
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
BIN = ROOT / ".venv" / "bin"
BRIDGE_EXE = BIN / "browser-bridge"
TOKEN_FILE = ROOT / ".token"
STATE_DIR = ROOT / ".bridge"
CLOUD_SKILL = ROOT / "skills" / "browser-bridge" / "SKILL.md"
CLOUD_SKILL_ZIP = STATE_DIR / "browser-bridge.zip"
LOCAL_URL = f"http://127.0.0.1:{os.environ.get('BRIDGE_PORT', '8765')}"
TUNNEL_ADDRESS = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")
START_TIMEOUT_S = 60
STOP_TIMEOUT_S = 10


@dataclass(frozen=True)
class Service:
    name: str

    @property
    def pid_file(self) -> Path:
        return STATE_DIR / f"{self.name}.pid"

    @property
    def log_file(self) -> Path:
        return STATE_DIR / f"{self.name}.log"

    def pid(self) -> int | None:
        """The running process's pid, or None (clearing a stale pid file)."""
        try:
            pid = int(self.pid_file.read_text())
            os.kill(pid, 0)
        except (FileNotFoundError, ValueError, ProcessLookupError):
            self.pid_file.unlink(missing_ok=True)
            return None
        except PermissionError:
            pass  # alive, owned by another user
        return pid

    def start(
        self, argv: list[str], ready: Callable[[], bool], env: dict[str, str] | None = None
    ) -> None:
        """Launch detached and wait until `ready()`; on failure, kill it and exit with its log."""
        STATE_DIR.mkdir(exist_ok=True)
        with self.log_file.open("w") as log:
            proc = subprocess.Popen(
                argv,
                cwd=ROOT,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        self.pid_file.write_text(str(proc.pid))
        # Poll our own child: until reaped, a crashed child still looks alive to os.kill(pid, 0).
        if _wait(lambda: ready() or proc.poll() is not None, START_TIMEOUT_S) and ready():
            return
        with contextlib.suppress(ProcessLookupError):
            os.killpg(proc.pid, signal.SIGKILL)
        proc.wait()
        self.pid_file.unlink(missing_ok=True)
        tail = "\n".join(self.log_file.read_text().splitlines()[-20:])
        sys.exit(f"error: the {self.name} did not come up. Last lines of {self.log_file}:\n{tail}")

    def stop(self) -> None:
        pid = self.pid()
        if pid is None:
            return
        os.kill(pid, signal.SIGTERM)  # the bridge closes its browser on SIGTERM
        if not _wait(lambda: self.pid() is None, STOP_TIMEOUT_S):
            with contextlib.suppress(ProcessLookupError):
                os.killpg(pid, signal.SIGKILL)
        self.pid_file.unlink(missing_ok=True)


BRIDGE = Service("bridge")
TUNNEL = Service("tunnel")


def _wait(condition: Callable[[], bool], timeout_s: float) -> bool:
    deadline = time.monotonic() + timeout_s
    while not condition():
        if time.monotonic() > deadline:
            return False
        time.sleep(0.5)
    return True


def _run(*argv: str | Path) -> None:
    print("$", " ".join(map(str, argv)), flush=True)
    subprocess.run(argv, cwd=ROOT, check=True)


def _local_status() -> int | None:
    """HTTP status of the bridge without a token (401 when up), or None if nothing listens."""
    no_proxy = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with no_proxy.open(f"{LOCAL_URL}/sessions", timeout=2) as response:
            return response.status
    except urllib.error.HTTPError as exc:
        return exc.code
    except OSError:
        return None


def _tunnel_address() -> str | None:
    if TUNNEL.pid() is None or not TUNNEL.log_file.exists():
        return None
    match = TUNNEL_ADDRESS.search(TUNNEL.log_file.read_text())
    return match.group() if match else None


def _write_cloud_skill(address: str) -> None:
    """Zip the cloud-session instructions with `address` filled in, ready to attach."""
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    note = (
        f"\n> **Tunnel address: `{address}`**, written when the bridge started ({stamp}).\n"
        "> It is filled in below and stops working when the tunnel restarts.\n"
    )
    text = CLOUD_SKILL.read_text().replace("<address>", address.removeprefix("https://"))
    lines = text.splitlines(keepends=True)
    title = next(i for i, line in enumerate(lines) if line.startswith("# "))
    lines.insert(title + 1, note)
    with zipfile.ZipFile(CLOUD_SKILL_ZIP, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("browser-bridge/SKILL.md", "".join(lines))


def setup() -> None:
    """A1 (install the bridge and its Chromium), A2 (check cloudflared), A3 (create .token)."""
    if not BRIDGE_EXE.exists():
        _run(sys.executable, "-m", "venv", ROOT / ".venv")
        _run(BIN / "pip", "install", "-e", ROOT)
    _run(BRIDGE_EXE, "install-browser")
    if not TOKEN_FILE.exists():
        fd = os.open(TOKEN_FILE, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as token:
            token.write(secrets.token_urlsafe(32))
        print(f"Created {TOKEN_FILE.name}")
    if not shutil.which("cloudflared"):
        sys.exit("error: cloudflared is not installed (README step A2)")
    print("Setup complete")


def start() -> None:
    """A4 (start the bridge) and A5 (start the tunnel), skipping whatever already runs."""
    if not BRIDGE_EXE.exists() or not TOKEN_FILE.exists():
        sys.exit("error: not set up yet; run `setup` first")
    if not shutil.which("cloudflared"):
        sys.exit("error: cloudflared is not installed (README step A2)")
    if BRIDGE.pid() is None:
        if _local_status() is not None:
            sys.exit(f"error: something else already listens on {LOCAL_URL}")
        env = {**os.environ, "BRIDGE_TOKEN": TOKEN_FILE.read_text().strip()}
        BRIDGE.start([str(BRIDGE_EXE)], lambda: _local_status() == 401, env)
    if TUNNEL.pid() is None:
        TUNNEL.start(
            ["cloudflared", "tunnel", "--url", LOCAL_URL], lambda: _tunnel_address() is not None
        )
    if address := _tunnel_address():
        _write_cloud_skill(address)
    status()


def status() -> None:
    for service in (BRIDGE, TUNNEL):
        pid = service.pid()
        print(f"{service.name}: {f'running (pid {pid})' if pid else 'stopped'}")
    print(f"tunnel address: {_tunnel_address() or '-'}")
    print(f"cloud skill: {CLOUD_SKILL_ZIP if CLOUD_SKILL_ZIP.exists() else '-'}")


def stop() -> None:
    TUNNEL.stop()
    BRIDGE.stop()
    CLOUD_SKILL_ZIP.unlink(missing_ok=True)
    status()


COMMANDS = {"setup": setup, "start": start, "status": status, "stop": stop}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=COMMANDS)
    try:
        COMMANDS[parser.parse_args().command]()
    except subprocess.CalledProcessError as exc:
        sys.exit(f"error: `{' '.join(map(str, exc.cmd))}` failed with exit code {exc.returncode}")


if __name__ == "__main__":
    main()
