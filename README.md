# cloud-browser-bridge

Let a cloud-hosted coding agent drive a browser **on your own machine**, over plain HTTPS.

```
cloud agent ──HTTPS + bearer token──▶ tunnel (e.g. Cloudflare) ──▶ 127.0.0.1:8765 bridge ──▶ Chromium window
```

Cloud agent sandboxes (such as Claude Code cloud sessions) usually reach the internet through an
egress proxy that allows only HTTPS to approved domains and does not support WebSocket upgrades.
That rules out attaching Playwright or Puppeteer to a remote Chrome over the DevTools protocol. This
bridge runs next to the browser and exposes a small HTTP API instead, which works through such
proxies.

- **Isolated browser.** Playwright's own Chromium with its own profile directory. It shares nothing
  with the browsers already on your machine: no cookies, sign-ins, extensions or history.
- **Visible.** The window shows on your screen by default, so you can watch, sign in, or solve a
  CAPTCHA yourself, then let the agent carry on.
- **Narrow API.** Open pages, read text and links, click, fill, press keys, go back, and take
  screenshots. No script execution, no file access.
- **Several agents at once.** Each caller session gets its own tab. Sign-ins are shared, pages are not.
- **Keeps off your LAN.** By default the browser refuses requests to loopback, private and
  link-local addresses, so a caller cannot reach your router, local services or cloud metadata.

> Independent open-source project. Not affiliated with or endorsed by Anthropic or Cloudflare.

## Quick start

### 1. Install (on the machine whose browser you want to use)

Python 3.10+ is required.

```bash
git clone https://github.com/riskand/cloud-browser-bridge.git
cd cloud-browser-bridge
python3 -m venv .venv && . .venv/bin/activate
pip install -e .
browser-bridge install-browser          # downloads Playwright's Chromium (~150 MB)
```

On Linux, if Chromium fails to start because of missing system libraries, run
`sudo .venv/bin/python -m playwright install-deps chromium`.

Also install [cloudflared](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/)
(`brew install cloudflared` on macOS, or the `.deb`/`.rpm` from Cloudflare's releases on Linux).
Any HTTPS tunnel works; this guide uses Cloudflare's free quick tunnels.

### 2. Create a token (once)

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))" > .token && chmod 600 .token
```

`.token` is git-ignored. Tokens shorter than 24 characters are rejected.

### 3. Run

```bash
# Terminal 1: the bridge. A Chromium window opens.
BRIDGE_TOKEN=$(cat .token) browser-bridge

# Terminal 2: the tunnel. Note the https://<random>.trycloudflare.com URL it prints.
cloudflared tunnel --url http://127.0.0.1:8765
```

Check the full path from anywhere:

```bash
curl -s -H "Authorization: Bearer $(cat .token)" https://<random>.trycloudflare.com/sessions
```

### 4. Configure the cloud agent's environment

Give the agent two environment variables and allow the tunnel's domain:

| Setting | Value |
|---|---|
| `BRIDGE_URL` | `https://<random>.trycloudflare.com` |
| `BRIDGE_TOKEN` | contents of `.token` |
| Network allowlist | `<random>.trycloudflare.com` |

Put the token in the environment's secret or variable settings, never in a chat or a committed file.

For **Claude Code cloud sessions**: open the environment menu in the session's title bar, choose
*Edit*, add both variables, and under *Network access* choose *Custom* and add the tunnel domain
(keep the default package-manager list). Environment changes apply to sessions started afterwards.

### 5. Tell the agent how to use it

Paste this into the agent's instructions (for example a `CLAUDE.md` in your repository):

```markdown
## Browser
A browser on the user's machine is reachable at $BRIDGE_URL. Every request needs
`Authorization: Bearer $BRIDGE_TOKEN` and `X-Bridge-Session: <a short name unique to this session>`.
POST /goto {"url"}, GET /text, GET /links, POST /click {"selector"}, POST /fill {"selector","value"},
POST /press {"key"}, POST /back, GET /screenshot. When done: DELETE /session.
Prefer /text and /links over screenshots. If a page shows a login or CAPTCHA, ask the user to
complete it in the bridge window, then continue.
```

A shell helper for the agent side:

```bash
br() { curl -sS -H "Authorization: Bearer $BRIDGE_TOKEN" -H "X-Bridge-Session: ${BR_SESSION:-default}" \
            -H "Content-Type: application/json" "$BRIDGE_URL$@"; }
br /goto -d '{"url":"https://example.com"}'
br /text
```

## API

All endpoints require `Authorization: Bearer <token>`. Endpoints that act on a page use the tab of
the session named in `X-Bridge-Session` (default `default`; letters, digits, `.`, `_`, `-`, up to 64
characters). The tab is created on first use.

| Method | Path | Body | Returns |
|---|---|---|---|
| POST | `/goto` | `{"url": "https://..."}` (http/https only) | `url`, `title`, HTTP `status` |
| GET | `/text` | | `url`, `title`, visible `text` (capped at 200,000 chars), `truncated` |
| GET | `/links` | | `url`, `title`, `links: [{text, href}]` |
| POST | `/click` | `{"selector": "..."}` | `url`, `title` after the click |
| POST | `/fill` | `{"selector": "...", "value": "..."}` | `url`, `title` |
| POST | `/press` | `{"key": "Enter"}` | `url`, `title` |
| POST | `/back` | | `url`, `title` |
| GET | `/screenshot?full_page=false` | | PNG image |
| GET | `/sessions` | | `sessions: {name: current url}` |
| DELETE | `/session` | | `closed: true/false` for the session in the header |

Selectors are [Playwright selectors](https://playwright.dev/docs/locators): CSS (`#id`,
`button[type=submit]`) or text (`text=Sign in`).

| Status | Meaning |
|---|---|
| 400 | Invalid `X-Bridge-Session` |
| 401 | Missing or wrong token |
| 422 | Invalid body, or the browser action failed (`{"error": "..."}`, e.g. a selector not found within the timeout, or a blocked private address) |
| 429 | Too many open sessions. Close one with `DELETE /session` |

Requests within one session run one at a time. Different sessions run concurrently.

## Configuration

| Variable | Default | |
|---|---|---|
| `BRIDGE_TOKEN` | random, printed at start | Bearer token, at least 24 characters |
| `BRIDGE_PORT` | `8765` | Always bound to `127.0.0.1` |
| `BRIDGE_PROFILE_DIR` | `~/.browser-bridge-profile` | Browser profile (sign-ins persist here) |
| `BRIDGE_HEADLESS` | off | `1` to run without a window |
| `BRIDGE_ALLOW_PRIVATE_NETWORKS` | off | `1` to let the browser reach loopback/LAN addresses, e.g. to test a local dev server |
| `BRIDGE_MAX_SESSIONS` | `8` | Maximum open tabs, including `default` |

## Security model

Read this before exposing the bridge.

- **The token is the only lock.** Whoever holds it controls the bridge's browser and every site
  signed in inside it. Keep it in `.token` and in the agent's secret settings only. Rotate it by
  generating a new one and updating both.
- **Sign in only to what the task needs.** Not your bank, not your primary email.
- **The browser is isolated from your other browsers**, not from your network identity. Sites see
  your IP address.
- **Private networks are blocked by default** for every request the browser makes (navigations,
  redirects, subresources). This is best effort: DNS rebinding with very short TTLs and WebSocket
  connections are not covered. Leave `BRIDGE_ALLOW_PRIVATE_NETWORKS` off unless you need it.
- **Run it only while you use it.** Stop both the bridge and the tunnel with `Ctrl+C`; the tunnel
  URL then stops working.
- To wipe everything the browser stored: `rm -rf ~/.browser-bridge-profile`.

Report vulnerabilities as described in [SECURITY.md](SECURITY.md).

## Limitations

- A Cloudflare quick tunnel gets a new URL every time `cloudflared` restarts, so the agent's
  environment and allowlist need updating each time. For a stable URL, use a
  [named tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/)
  on a domain you control.
- Links that open a new window (`target="_blank"`) open outside the session's tab and are not
  tracked. Use `/goto` with the link's `href` from `/links` instead.
- No file uploads or downloads, no multi-tab control within a session.
- Sites with strong bot protection may still challenge the browser. Solve it in the window.

## Development

```bash
pip install -e ".[dev]"
browser-bridge install-browser
ruff check . && ruff format --check .
pytest
```

The tests start real headless Chromium instances against a local web server.

## Contributing

Issues and pull requests are welcome. Fork the repository, make your change on a branch, and open a
pull request against `main`. CI (lint and tests) must pass and the maintainer must approve before
it is merged. For security problems, follow [SECURITY.md](SECURITY.md) instead of opening an issue.

## License

[MIT](LICENSE)
