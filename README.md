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

## Setup

There are three parts: **A** runs the bridge on your machine, **B** lets your cloud agent reach it,
**C** checks that it works. Part B is written for Claude Code cloud sessions;
[other agents](#other-cloud-agents) follow at the end.

### A. On your machine

You need Python 3.10+ and about 300 MB of disk space for the browser.

> **With Claude Code on this machine**, you can skip the manual steps below: after `git clone`, run
> `claude` in the repository and ask it to *start the bridge* (or type `/bridge`). The project skill
> in `.claude/skills/bridge/` runs A1 to A5, keeps both processes in the background, and prints your
> tunnel address. Ask it to *stop the bridge* when you are done. Installing `cloudflared` with
> `sudo` (A2) is left to you.

**A1. Install the bridge (once)**

```bash
git clone https://github.com/riskand/cloud-browser-bridge.git
cd cloud-browser-bridge
python3 -m venv .venv && . .venv/bin/activate
pip install -e .
browser-bridge install-browser
```

`install-browser` downloads Playwright's own Chromium. It does not touch a browser you already have.
On Linux, if Chromium later fails to start because of missing system libraries, run
`sudo .venv/bin/python -m playwright install-deps chromium`.

**A2. Install cloudflared (once)**

Debian or Ubuntu:

```bash
curl -fsSLo /tmp/cloudflared.deb \
  https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i /tmp/cloudflared.deb
```

macOS: `brew install cloudflared`. Other systems: see
[Cloudflare's downloads page](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/).
Check with `cloudflared --version`.

**A3. Create a token (once)**

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))" > .token && chmod 600 .token
```

This is the password to your bridge. `.token` is git-ignored. Never paste it into a chat.

**A4. Start the bridge (every time)**

```bash
cd cloud-browser-bridge && . .venv/bin/activate
BRIDGE_TOKEN=$(cat .token) browser-bridge
```

A Chromium window opens on `about:blank`. Leave this terminal running.

**A5. Start the tunnel (every time)**

In a second terminal:

```bash
cloudflared tunnel --url http://127.0.0.1:8765
```

After a few seconds it prints a box containing your address, for example
`https://beta-marco-queue-flying.trycloudflare.com`. Copy it; Part B calls it **your tunnel
address**. Leave this terminal running too. Warnings about `ICMP proxy` or `ping_group_range` are
harmless.

The address changes every time you restart `cloudflared`. See
[When the tunnel address changes](#when-the-tunnel-address-changes).

### B. In Claude Code (cloud session)

Both settings live in your cloud environment and apply to every session that uses it, including
sessions already running.

> **Let Claude guide you.** [`skills/browser-bridge`](skills/browser-bridge/SKILL.md) is a skill for
> the cloud session. It checks the connection, walks you through B2 and B3 one step at a time based
> on the error it sees, and then teaches the agent the API, so B4 is not needed. Add it in either
> of two ways:
>
> - Copy the `skills/browser-bridge` folder into `.claude/skills/` of the repository you work on in
>   the cloud. Every session of that repository then has it.
> - Upload `.bridge/browser-bridge.zip` as a skill in your claude.ai settings, so it follows you to
>   every session. The local `bridge` skill writes it on every start with your current tunnel address
>   filled in, so upload it again after each restart; the new upload replaces the old one. It never
>   contains the token: that stays in the network secret (B3).
>
> Then ask the agent to *set up the browser bridge*.

**B1. Open the environment settings**

On the session's page at claude.ai/code, click the small arrow next to the repository name at the top
left (or the grey label showing your environment name, such as `Default · your-repo`), then choose
**Edit cloud environment**.

**B2. Allow the tunnel's domain**

1. **Network access**: change it to **Custom**.
2. **Allowed domains**: add `*.trycloudflare.com`. The wildcard means a new tunnel address needs no
   change here.
3. Keep **Also include default list of common package managers** ticked, or package installs in your
   sessions stop working.
4. Click **Save changes**.

**B3. Add the token as a network secret**

A network secret makes Claude Code's proxy add your token to requests for you, so the token never
enters the cloud session where the agent or its tools could read or leak it.

1. Open **Edit cloud environment** again. Under **Network secrets**, click **Add secret**.
2. Fill in the form:

   | Field | Value |
   |---|---|
   | Name | `browser-bridge` |
   | Secret type | `Bearer` |
   | Allowed websites | your tunnel address **without** `https://`, e.g. `beta-marco-queue-flying.trycloudflare.com` |
   | Path prefixes | leave empty |
   | Custom header: Name | `Authorization` |
   | Custom header: Prefix | `Bearer` |
   | Custom header: Value | the contents of `.token` (run `cat .token` and copy it) |

3. Click **Add**, then **Save changes**.

Watch for these mistakes:

- **Header name must be `Authorization`**, not `Authentication`.
- **Clear the Value field before pasting.** Browsers sometimes auto-fill a saved password into it.
- **Do not use a wildcard in Allowed websites.** With `*.trycloudflare.com` the proxy would send your
  token to every trycloudflare address the agent visits, including tunnels run by strangers. Use the
  exact address.

**B4. Tell the agent where the browser is**

Paste this into the agent's instructions, for example a `CLAUDE.md` in your repository, and replace
the address:

```markdown
## Browser
A browser on the user's machine is reachable at https://<your-tunnel-address>.
The network proxy adds the Authorization header automatically; do not send one.
Send `X-Bridge-Session: <a short name unique to this session>` on every request.
POST /goto {"url"}, GET /text, GET /links, POST /click {"selector"}, POST /fill {"selector","value"},
POST /press {"key"}, POST /back, GET /screenshot. When done: DELETE /session.
Prefer /text and /links over screenshots. If a page shows a login or CAPTCHA, ask the user to
complete it in the bridge window, then continue.
```

Or just give the address to the agent in your message.

### C. Check that it works

Ask the agent to run:

```bash
curl -sS -H "X-Bridge-Session: test" https://<your-tunnel-address>/sessions
curl -sS -H "X-Bridge-Session: test" -H "Content-Type: application/json" \
     -d '{"url":"https://example.com"}' https://<your-tunnel-address>/goto
```

The first should return `{"sessions":{...}}` and the second `"title":"Example Domain"`. A new tab
with example.com appears in the bridge window. If not, see [Troubleshooting](#troubleshooting).

### When the tunnel address changes

Every `cloudflared` restart gives a new address. Then:

1. In **Edit cloud environment → Network secrets**, edit `browser-bridge` and replace the address in
   **Allowed websites**.
2. Give the agent the new address. If you use the uploaded skill, upload the new
   `.bridge/browser-bridge.zip` instead; it replaces the old one.

The allowlist from B2 already covers it. For an address that never changes, use a
[named tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/)
on a domain you own.

### Stop

Press `Ctrl+C` in both terminals. The tunnel address stops working immediately. To also wipe
everything the bridge's browser stored, including sign-ins: `rm -rf ~/.browser-bridge-profile`.

### Other cloud agents

Any agent that can make HTTPS requests works. It needs:

1. Its network allowlist to include your tunnel address.
2. The token, ideally injected by its platform as an `Authorization: Bearer <token>` header. If the
   platform can't inject headers, store the token as a secret environment variable such as
   `BRIDGE_TOKEN` and have the agent send the header itself.

A shell helper that works either way:

```bash
br() {
  local auth=()
  [ -n "$BRIDGE_TOKEN" ] && auth=(-H "Authorization: Bearer $BRIDGE_TOKEN")
  curl -sS "${auth[@]}" -H "X-Bridge-Session: ${BR_SESSION:-default}" \
       -H "Content-Type: application/json" "$BRIDGE_URL$@"
}
BRIDGE_URL=https://<your-tunnel-address>
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
  signed in inside it. Keep it in `.token` and in your platform's secret settings only, scoped to
  your exact tunnel address. Rotate it by generating a new `.token`, restarting the bridge, and
  updating the secret.
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

## Troubleshooting

| What the agent sees | Cause | Fix |
|---|---|---|
| `CONNECT tunnel failed, response 403` | The cloud environment blocks the domain | B2: add `*.trycloudflare.com` to Allowed domains and save |
| `{"detail":"missing or wrong bearer token"}` (401) | The token isn't arriving or doesn't match | B3: check the header name is `Authorization`, the prefix is `Bearer`, Allowed websites is the current tunnel address, and the value matches `.token`. If you started the bridge without `BRIDGE_TOKEN`, it made up a new token; restart it with `BRIDGE_TOKEN=$(cat .token)` |
| Cloudflare error page, `502` or `530` | The bridge or the tunnel is not running | Check both terminals from A4 and A5 are still running |
| It worked, then 401 or 403 after a restart | The tunnel address changed | [When the tunnel address changes](#when-the-tunnel-address-changes) |
| `ERR_BLOCKED_BY_CLIENT` (422) | The page is on a private or local address | Intended. To allow it, start the bridge with `BRIDGE_ALLOW_PRIVATE_NETWORKS=1` |
| `Timeout ... exceeded` (422) | The selector matched nothing within 15s | Check the selector against `/text` or `/screenshot` |
| `at most 8 sessions can be open` (429) | Too many tabs | `DELETE /session` for finished sessions, or close tabs in the window |

## Limitations

- A Cloudflare quick tunnel gets a new address every time `cloudflared` restarts, so the network
  secret needs updating each time (see above). Quick tunnels also come with no uptime guarantee.
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
