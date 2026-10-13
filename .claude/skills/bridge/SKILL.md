---
name: bridge
description: Set up, start, stop or check the browser bridge and its Cloudflare quick tunnel on this machine (README Part A). Use when the user asks to install, start, restart, stop or check the bridge or the tunnel, or asks for the tunnel address.
argument-hint: "[setup|start|status|stop]"
allowed-tools: Bash(python3 .claude/skills/bridge/scripts/bridge.py:*)
---

# Browser bridge: Part A

`scripts/bridge.py` runs README Part A on this machine (macOS or Linux). Run it from the repository
root with the system Python. It needs only the standard library.

```bash
python3 .claude/skills/bridge/scripts/bridge.py <command>
```

| Command | What it does |
|---|---|
| `setup` | A1: creates `.venv` and installs the bridge. It drives the Google Chrome already on this machine; with `BRIDGE_BROWSER=chromium` it downloads Playwright's Chromium instead (about 300 MB). A3: creates `.token` if missing. A2: checks that `cloudflared` is installed. Safe to re-run. |
| `start` | A4 and A5: starts the bridge and the tunnel in the background, waits until both are up and prints the tunnel address. Writes `.bridge/browser-bridge.zip`, the cloud-session instructions with that address filled in. Leaves anything already running alone. |
| `status` | Shows which of the two is running and the current tunnel address. |
| `stop` | Stops the tunnel, then the bridge, and deletes the zip. |

Both processes keep running after Claude Code exits. Logs and pid files are in `.bridge/`.

## Steps

1. For a restart, run `stop` first. Otherwise go straight to `start`: it leaves running processes
   alone and still rewrites the zip.
2. Run `start`.
   - If it says the project is not set up yet, run `setup` (ask first if `BRIDGE_BROWSER=chromium`,
     which downloads about 300 MB), then `start` again.
   - If `cloudflared` is missing: on macOS with Homebrew, offer to run `brew install cloudflared`.
     Otherwise installing it needs `sudo`, so give the user the commands from README step A2 to run
     in their own terminal.
3. Reply with exactly one of these, filling in the address and the zip's full path, and nothing
   more. If `start` printed `new tunnel address`:

   > Bridge running at `<tunnel address>` (new address). Chrome is minimized in your taskbar.
   >
   > - **New cloud session:** attach `<full path of .bridge/browser-bridge.zip>` and say
   >   **set up browser with the attached zip**.
   > - **Session that already used the bridge:** attach the same zip there and say
   >   **reset browser with the attached zip**.

   Otherwise the address is unchanged:

   > Bridge already running at `<tunnel address>`. Sessions already set up keep working.
   > For a new cloud session, attach `<full path of .bridge/browser-bridge.zip>` and say
   > **set up browser with the attached zip**.

   Background, only if the user asks: the zip holds the cloud-session instructions with this address
   filled in, everything needed to connect except the token. It is attached to each cloud session,
   not installed as a skill. The token stays in the user's `browser-bridge` network secret; after a
   restart only the secret's **Allowed websites** changes, and the cloud session guides that.

## Rules

- Never read, print or `cat` `.token`, and never put its value in a command. The script passes it to
  the bridge itself. If the user needs the token, tell them to copy it from their own terminal.
- Never run `sudo`. Hand those commands to the user.
- Bridge options are `BRIDGE_*` environment variables (README "Configuration"). Put them in front of
  `start`, for example `BRIDGE_HEADLESS=1 python3 .claude/skills/bridge/scripts/bridge.py start`.
  They take effect only on a fresh start, so run `stop` first if the bridge is already running.
- If `start` fails, it prints the end of the relevant log. Diagnose from that:
  - Something else is already using the port, often a bridge started by hand: ask the user to stop it,
    or start with a different `BRIDGE_PORT`.
  - `Chromium distribution 'chrome' is not found`: Google Chrome is not installed. Ask the user to
    install it the usual way (google.com/chrome), or to use Playwright's Chromium instead: `stop`,
    then `BRIDGE_BROWSER=chromium` in front of both `setup` and `start`. Don't run
    `playwright install chrome`: it replaces the system's Chrome and needs `sudo`.
  - On Linux, Chromium may be missing system libraries. The user can install them with
    `sudo .venv/bin/python -m playwright install-deps chromium`.
