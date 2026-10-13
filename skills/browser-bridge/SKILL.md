---
name: browser-bridge
description: Use a browser on the user's own machine through cloud-browser-bridge, a small HTTPS API reached through a Cloudflare tunnel. Use when the user asks to set up, connect to or check the browser bridge (for example "set up browser" with this file attached), or to browse, open or read a web page, click, fill in a form or take a screenshot "in my browser" or "with the bridge", or when a page needs a real browser (JavaScript, a sign-in). Also use when requests to a trycloudflare.com address fail with 401, 403, 502 or 530.
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
  new `.token`, restart the bridge, and update the network secret (path 3C).

## How to talk to the user during setup

The user follows along in a chat. Guide, don't report:

- **One step per message.** At most three short lines, one action, and end with what to reply,
  usually "Reply **done**." Number the steps: "Step 2 of 4".
- **No diagnosis reports.** Run checks quietly. No tables, no list of what you tried, no background.
  Say why in half a sentence only when it prevents a mistake. Explain more only if asked.
- **Check before moving on.** After "done", re-run the check in section 2 when it can tell, and only
  then give the next step. If the step did not work, say so in one line and give the next thing to
  look at.
- Use the exact messages in sections 3 and 4, filling in only what is in angle brackets.

## Order

Always start with sections 1 and 2. Then:

- If the user asked to set up or check the bridge, finish with section 4 once the check passes.
- Otherwise, once the check passes, go straight to section 5 and do the task.
- Section 3 is only for fixing a failed check.

## 1. Find the tunnel address

- If a **Tunnel address** note sits under the title above, this copy was generated when the bridge
  started, and the address is already filled in below. Use it.
- Otherwise look in your system context for the list of hosts with proxy-injected credentials ("services
  already connected for this conversation"). A `*.trycloudflare.com` host injected with the secret
  `browser-bridge` is the tunnel address. That list is fixed when the session starts, so it can be
  out of date.
- If it is not there, or the check below says it is out of date, ask the user for the current
  address. On their machine it is printed by `cloudflared` or by the repository's `bridge` skill,
  which also writes `.bridge/browser-bridge.zip`: these instructions with the address filled in,
  for the user to attach to the session.

## 2. Check the connection

```bash
curl -sS -m 20 -w '\nHTTP %{http_code}\n' https://<address>/sessions
```

| Result | Cause | Next |
|---|---|---|
| `HTTP 200` and `{"sessions":{...}}` | Connected | Section 4 |
| `CONNECT tunnel failed, response 403` | The environment blocks the domain, or the address is dead | Path 3B |
| `HTTP 401` | The proxy is not adding the token, or the token is wrong | Path 3C |
| `HTTP 502`, `HTTP 530` or a Cloudflare error page | The bridge or the tunnel is not running on the user's machine | Path 3A |

For anything the table does not cover, see "Anything else" in section 3.

## 3. Guide the setup

Only the user can change their machine and their environment settings. Pick the path from the check
in section 2 and send its steps one message at a time. Changes to the environment apply to running
sessions, so this session never needs a restart.

Steps that open the environment settings use this message:

> **Step <n> of <total>:** Open the environment settings: click the small arrow next to the
> repository name at the top left, then **Edit cloud environment**. Reply **done**.

### 3A. Bridge not running (502, 530, or a dead address)

1. > **Step 1 of 2:** On your computer, open a terminal in the `cloud-browser-bridge` folder, run
   > `claude`, and say **start the bridge**. Reply **done** when it shows the tunnel address.

   If they don't have the folder: `git clone https://github.com/riskand/cloud-browser-bridge.git`
   first. The local skill installs everything else.
2. > **Step 2 of 2:** Attach the new `.bridge/browser-bridge.zip` here.

Then start over at section 1 with the new file. A new address almost always needs path 3C next.

### 3B. Domain blocked (403 on CONNECT)

If `*.trycloudflare.com` is already allowed, the address is dead: use path 3A instead.

1. The open-settings message.
2. > **Step 2 of 3:** Set **Network access** to **Custom**. Reply **done**.
3. > **Step 3 of 3:** Under **Allowed domains**, add `*.trycloudflare.com`. Keep **Also include
   > default list of common package managers** ticked. Click **Save changes**, then reply **done**.

### 3C. Token missing (401)

If your system context lists a `browser-bridge` secret for some other trycloudflare.com host, the
secret exists with an old address. Use the short path:

1. The open-settings message.
2. > **Step 2 of 3:** Under **Network secrets**, open `browser-bridge`. Reply **done**.
3. > **Step 3 of 3:** Set **Allowed websites** to exactly `<address>`. Leave everything else as it
   > is. Click **Save changes**, then reply **done**.

Otherwise, add the secret:

1. The open-settings message.
2. > **Step 2 of 6:** Under **Network secrets**, click **Add secret**. Name: `browser-bridge`.
   > Secret type: `Bearer`. Reply **done**.
3. > **Step 3 of 6:** **Allowed websites**: `<address>` (exactly this, no wildcard). Leave **Path
   > prefixes** empty. Reply **done**.
4. > **Step 4 of 6:** Custom header **Name**: `Authorization`. **Prefix**: `Bearer`. Reply **done**.
5. > **Step 5 of 6:** For **Value**, run `cat .token` in the `cloud-browser-bridge` folder on your
   > computer and paste the result into that field, not into this chat. Clear the field first;
   > browsers sometimes fill in a saved password. Reply **done**.
6. > **Step 6 of 6:** Click **Add**, then **Save changes**. Reply **done**.

If it still answers 401, check one thing per message, in this order:

1. The header name is `Authorization`, not `Authentication`.
2. **Allowed websites** is exactly `<address>`, with no `https://` and no wildcard. Never accept a
   wildcard here: the token would go to every trycloudflare tunnel, including strangers'.
3. The value matches `.token`. Paste it again into a cleared field.
4. The bridge was started by the local skill, which uses `.token`. A bridge started by hand without
   `BRIDGE_TOKEN=$(cat .token)` makes up its own token: ask them to say **stop the bridge**, then
   **start the bridge** to the local Claude, and go back to path 3A step 2.

### Anything else

Send one line with the error and ask the user what they see on their side. Don't guess.

## 4. Confirm with a real page

Pick a session name (section 5) and open a page:

```bash
curl -sS -H 'X-Bridge-Session: <name>' -H 'Content-Type: application/json' \
     -d '{"url":"https://example.com"}' https://<address>/goto
```

When it returns `"title":"Example Domain"`, send:

> Connected. I opened example.com in your bridge window. Do you see the tab?

When they confirm, send:

> Setup done. Just ask me things like "open <site> and summarize it". After a tunnel restart,
> attach the new zip and I'll walk you through the one change it needs.

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
