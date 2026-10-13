# Security policy

The bridge lets a remote caller control a browser on your machine, so security reports are taken
seriously.

## Reporting a vulnerability

Please do **not** open a public issue. Use GitHub's private vulnerability reporting instead:
the repository's **Security** tab → **Report a vulnerability**.

Include what an attacker needs (for example: a valid token, network position, a malicious page),
what they gain, and steps to reproduce. You should get a first response within a week.

## In scope

- Bypassing the bearer-token check
- Escaping the private-network guard while `BRIDGE_ALLOW_PRIVATE_NETWORKS` is off
- Reading local files or running code on the host through the API
- Anything that lets the bridge's browser access data from the host's other browsers

## Known limitations (not vulnerabilities)

These are documented in the README's security model:

- Whoever holds the token controls the bridge's browser and its signed-in sites.
- The private-network guard is best effort against DNS rebinding and does not cover WebSockets.
- Sites see the host's IP address.
