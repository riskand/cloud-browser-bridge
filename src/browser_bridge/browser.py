"""The browser and its per-session tabs."""

import asyncio
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from playwright.async_api import BrowserContext, Page, async_playwright

from .config import Settings
from .network_guard import PrivateNetworkGuard

DEFAULT_SESSION = "default"
SESSION_ID = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")


class SessionLimitReached(Exception):
    pass


class Tabs:
    """One tab per caller session, all in one browser context so sign-ins are shared.

    Requests within a session run one at a time, so a session never reads a page halfway
    through its own previous action. Different sessions run concurrently.
    """

    def __init__(self, context: BrowserContext, max_sessions: int) -> None:
        self._context = context
        self._max_sessions = max_sessions
        self._pages: dict[str, Page] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._registry_lock = asyncio.Lock()
        if context.pages:
            self._pages[DEFAULT_SESSION] = context.pages[0]

    @asynccontextmanager
    async def use(self, session_id: str) -> AsyncIterator[Page]:
        async with self._locks.setdefault(session_id, asyncio.Lock()):
            yield await self._page_for(session_id)

    async def _page_for(self, session_id: str) -> Page:
        page = self._pages.get(session_id)
        if page and not page.is_closed():
            return page
        async with self._registry_lock:
            self._prune()
            if len(self._pages) >= self._max_sessions:
                raise SessionLimitReached(f"at most {self._max_sessions} sessions can be open")
            page = await self._context.new_page()
            self._pages[session_id] = page
            return page

    def open_sessions(self) -> dict[str, str]:
        self._prune()
        return {session_id: page.url for session_id, page in self._pages.items()}

    async def close(self, session_id: str) -> bool:
        async with self._locks.setdefault(session_id, asyncio.Lock()):
            page = self._pages.pop(session_id, None)
            if page is None or page.is_closed():
                return False
            await page.close()
            return True

    def _prune(self) -> None:
        """Forget tabs the person closed by hand in the window, and idle locks."""
        self._pages = {sid: page for sid, page in self._pages.items() if not page.is_closed()}
        self._locks = {
            sid: lock for sid, lock in self._locks.items() if sid in self._pages or lock.locked()
        }


@asynccontextmanager
async def launch(settings: Settings) -> AsyncIterator[Tabs]:
    async with async_playwright() as playwright:
        context = await playwright.chromium.launch_persistent_context(
            str(settings.profile_dir), headless=settings.headless
        )
        try:
            context.set_default_timeout(settings.action_timeout_ms)
            context.set_default_navigation_timeout(settings.navigation_timeout_ms)
            if not settings.allow_private_networks:
                await context.route("**/*", PrivateNetworkGuard().route)
            yield Tabs(context, settings.max_sessions)
        finally:
            await context.close()
