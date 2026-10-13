"""Command line: `browser-bridge` (serve) or `browser-bridge install-browser`."""

import argparse
import subprocess
import sys

import uvicorn

from .api import create_app
from .config import Settings, browser_from_env

HOST = "127.0.0.1"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="browser-bridge",
        description="Drive an isolated browser on this machine over a token-protected HTTP API. "
        "Configure with BRIDGE_* environment variables (see README).",
    )
    parser.add_argument("command", nargs="?", default="serve", choices=["serve", "install-browser"])
    args = parser.parse_args(argv)

    if args.command == "install-browser":
        browser = browser_from_env()
        if browser != "chromium":
            print(f"Using the {browser} installed on this machine; nothing to download.")
            print("Set BRIDGE_BROWSER=chromium to use Playwright's own Chromium instead.")
            return
        sys.exit(subprocess.call([sys.executable, "-m", "playwright", "install", "chromium"]))

    try:
        settings = Settings.from_env()
    except ValueError as exc:
        parser.error(str(exc))
    if settings.token_generated:
        print(f"\nBRIDGE_TOKEN={settings.token}\n(set BRIDGE_TOKEN to keep it across restarts)\n")
    print(f"Profile: {settings.profile_dir}  Listening: http://{HOST}:{settings.port}", flush=True)
    uvicorn.run(create_app(settings), host=HOST, port=settings.port)


if __name__ == "__main__":
    main()
