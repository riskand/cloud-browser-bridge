---
name: browser-bridge
description: Use a browser on the user's own machine through cloud-browser-bridge, a small HTTPS API reached through a Cloudflare tunnel. Use when the user asks to browse, open or read a web page, click, fill in a form or take a screenshot "in my browser" or "with the bridge", or when a page needs a real browser (JavaScript, a sign-in). Also use to connect this cloud session to the bridge for the first time, and when requests to a trycloudflare.com address fail with 401, 403, 502 or 530.
---

# Browser bridge (cloud session)

The user runs [cloud-browser-bridge](https://github.com/riskand/cloud-browser-bridge) on their own
machine: an isolated Chromium window behind a token-protected HTTP API, published through a
Cloudflare quick tunnel at an address like `https://<four-words>.trycloudflare.com`. This session
reaches it with `curl`.

The token never enters this session. The environment's network proxy adds
`Authorization: Bearer <token>` to requests for the tunnel address. So:

- Never send an `Authorization` header yourself.
- Never ask the user to paste the token into the chat. If they do, tell them to rotate it: create a
  new `.token`, restart the bridge, and update the network secret (step 3C).

Always start with sections 1 and 2. When the check passes, go straight to section 5. Sections 3 and 4
are only for setting up or repairing the connection.

## 1. Find the tunnel address

- Look in your system context for the list of hosts with proxy-injected credentials ("services
  already connected for this conversation"). A `*.trycloudflare.com` host injected with the secret
  `browser-bridge` is the tunnel address. That list is fixed when the session starts, so it can be
  out of date.
- If it is not there, or the check below says it is out of date, ask the user for the current
  address. On their machine it is printed by `cloudflared` or by the repository's `bridge` skill.

## 2. Check the connection

```bash
curl -sS -m 20 -w '\nHTTP %{http_code}\n' https://<address>/sessions
```

| Result | Cause | Next |
|---|---|---|
| `HTTP 200` and `{"sessions":{...}}` | Connected | Section 4 |
| `CONNECT tunnel failed, response 403` | The environment blocks the domain, or the address is dead | Step 3B. If the domain is already allowed, ask for the current address (step 3A) |
| `HTTP 401` | The proxy is not adding the token, or the token is wrong | Step 3C |
| `HTTP 502`, `HTTP 530` or a Cloudflare error page | The bridge or the tunnel is not running on the user's machine | Step 3A |

Do not guess a fix from the error alone when the table does not cover it. Show the user the output.

## 3. Guide the setup

Only the user can change their machine and their environment settings. Give one step at a time, wait
until they say it is done, then run the check in section 2 again. Changes to the environment apply
to running sessions, so there is no need to restart this one.

### 3A. Run the bridge on their machine

If the bridge is not set up yet, it needs Python 3.10+ and `cloudflared`:

```bash
git clone https://github.com/riskand/cloud-browser-bridge.git
cd cloud-browser-bridge
claude
```

Then they ask that local Claude Code to *start the bridge*. It installs what is missing, creates the
token file `.token`, starts the bridge and the tunnel, and prints the tunnel address. Without Claude
Code, they can follow Part A of the repository's README.

The address changes every time the tunnel restarts. With a new address, the network secret must be
updated too (step 3C, **Allowed websites**).

### 3B. Allow the tunnel's domain

1. On this session's page at claude.ai/code, click the small arrow next to the repository name at
   the top left (or the grey environment label), then **Edit cloud environment**.
2. **Network access**: **Custom**.
3. **Allowed domains**: add `*.trycloudflare.com`. The wildcard means a new tunnel address needs no
   change here.
4. Keep **Also include default list of common package managers** ticked.
5. **Save changes**.

### 3C. Add the token as a network secret

In **Edit cloud environment**, under **Network secrets**, click **Add secret** (or edit the existing
`browser-bridge` secret):

| Field | Value |
|---|---|
| Name | `browser-bridge` |
| Secret type | `Bearer` |
| Allowed websites | the tunnel address **without** `https://`, e.g. `four-random-words-here.trycloudflare.com` |
| Path prefixes | empty |
| Custom header: Name | `Authorization` |
| Custom header: Prefix | `Bearer` |
| Custom header: Value | the contents of `.token`, copied by the user on their machine |

Then **Add** and **Save changes**. Point out the usual mistakes:

- The header name is `Authorization`, not `Authentication`.
- Clear the **Value** field before pasting. Browsers sometimes auto-fill a saved password into it.
- Never a wildcard in **Allowed websites**. With `*.trycloudflare.com` the token would go to every
  tunnel the session visits, including strangers'. Use the exact address.
- If the bridge was started without `.token`, it made up its own token. Restarting it through the
  `bridge` skill (or with `BRIDGE_TOKEN=$(cat .token)`) fixes that.

## 4. Confirm with a real page

Pick a session name (section 5) and open a page:

```bash
curl -sS -H 'X-Bridge-Session: <name>' -H 'Content-Type: application/json' \
     -d '{"url":"https://example.com"}' https://<address>/goto
```

Expect `"title":"Example Domain"`. Ask the user whether a tab with example.com appeared in the bridge
window. Setup is done; tell them that, and that the only thing to repeat after a tunnel restart is
updating **Allowed websites** in the secret.

## 5. Use the bridge

Shell state does not persist between commands, so write the address and the session name out in
every command.

**Session name.** Send `X-Bridge-Session: <name>` on every request. Use one short name for this whole
session, unique to it (letters, digits, `.`, `_`, `-`; up to 64), such as `claude-<task>-<4 random
characters>`. Each name gets its own tab. Sign-ins are shared between tabs.

```bash
curl -sS -H 'X-Bridge-Session: <name>' -H 'Content-Type: application/json' \
     -d '<json body>' https://<address>/<path>
```

| Method | Path | Body | Returns |
|---|---|---|---|
| POST | `/goto` | `{"url": "https://..."}` | `url`, `title`, HTTP `status` |
| GET | `/text` | | `url`, `title`, visible `text` (up to 200,000 characters), `truncated` |
| GET | `/links` | | `url`, `title`, `links: [{text, href}]` |
| POST | `/click` | `{"selector": "..."}` | `url`, `title` after the click |
| POST | `/fill` | `{"selector": "...", "value": "..."}` | `url`, `title` |
| POST | `/press` | `{"key": "Enter"}` | `url`, `title` |
| POST | `/back` | | `url`, `title` |
| GET | `/screenshot?full_page=false` | | PNG image |
| GET | `/sessions` | | open sessions and their current URLs |
| DELETE | `/session` | | closes this session's tab |

Selectors are Playwright selectors: CSS (`#id`, `button[type=submit]`) or text (`text=Sign in`).

Working rules:

- Read pages with `/text` and `/links`. Take a screenshot only when layout matters: save it with
  `-o <file>.png` and open the file to look at it.
- Links that open a new window are not followed. Use `/goto` with the `href` from `/links`.
- On a login page, a CAPTCHA or a cookie wall you cannot get past, ask the user to deal with it in the
  bridge window, then carry on.
- Ask before submitting forms that send, buy, post or change anything for the user.
- When the task is done, close the tab: `curl -sS -X DELETE -H 'X-Bridge-Session: <name>'
  https://<address>/session`.

| Error | Meaning |
|---|---|
| 422 `Timeout ... exceeded` | The selector matched nothing within 15 seconds. Check it against `/text` |
| 422 `ERR_BLOCKED_BY_CLIENT` | The page is on a private or local address, which the bridge blocks by default |
| 429 | Too many open tabs. Close finished sessions with `DELETE /session` |
| 401, 403, 502, 530 | The connection broke. Go back to section 2 |
