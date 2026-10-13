"""Keeps the browser off the bridge host's own network.

A caller holding the token controls where the browser goes. Without this guard it could make the
browser load the host's router admin page, a local dev server, or cloud metadata endpoints.
Every request (navigations, redirects, subresources) is checked; anything resolving to a
loopback, private, link-local or otherwise non-global address is aborted.

Best effort: the browser does its own DNS lookup after this check, so a DNS-rebinding attacker
with a very short TTL could still slip through. WebSocket connections are not checked.
"""

import asyncio
import ipaddress
import socket
import time
from urllib.parse import urlsplit

from playwright.async_api import Route

CACHE_TTL_SECONDS = 60.0


class PrivateNetworkGuard:
    def __init__(self) -> None:
        self._cache: dict[str, tuple[bool, float]] = {}

    async def route(self, route: Route) -> None:
        if await self.is_public(route.request.url):
            await route.continue_()
        else:
            await route.abort("blockedbyclient")

    async def is_public(self, url: str) -> bool:
        host = urlsplit(url).hostname
        if not host:
            return False
        now = time.monotonic()
        cached = self._cache.get(host)
        if cached and cached[1] > now:
            return cached[0]
        public = await _resolves_to_public(host)
        self._cache[host] = (public, now + CACHE_TTL_SECONDS)
        return public


async def _resolves_to_public(host: str) -> bool:
    try:
        return _is_public(host)
    except ValueError:
        pass  # not an IP literal
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(host, None)
    except socket.gaierror:
        return True  # unresolvable: let the browser fail with its own DNS error
    return all(_is_public(info[4][0]) for info in infos)


def _is_public(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return ip.is_global
