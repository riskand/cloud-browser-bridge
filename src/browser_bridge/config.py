"""Bridge settings, read once from environment variables."""

import os
import secrets
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

MIN_TOKEN_LENGTH = 24
DEFAULT_BROWSER = "chrome"


def default_profile_dir(browser: str) -> Path:
    """One profile per browser: Chrome and Playwright's Chromium can't share one across versions."""
    return Path.home() / f".browser-bridge-{browser}-profile"


def browser_from_env(env: Mapping[str, str] = os.environ) -> str:
    return env.get("BRIDGE_BROWSER", "").strip().lower() or DEFAULT_BROWSER


@dataclass(frozen=True)
class Settings:
    token: str
    token_generated: bool = False
    port: int = 8765
    browser: str = DEFAULT_BROWSER
    profile_dir: Path = default_profile_dir(DEFAULT_BROWSER)
    headless: bool = False
    allow_private_networks: bool = False
    max_sessions: int = 8
    action_timeout_ms: int = 15_000
    navigation_timeout_ms: int = 30_000

    @classmethod
    def from_env(cls, env: Mapping[str, str] = os.environ) -> "Settings":
        token = env.get("BRIDGE_TOKEN", "")
        if token and len(token) < MIN_TOKEN_LENGTH:
            raise ValueError(f"BRIDGE_TOKEN must be at least {MIN_TOKEN_LENGTH} characters")
        browser = browser_from_env(env)
        profile_dir = env.get("BRIDGE_PROFILE_DIR") or default_profile_dir(browser)
        return cls(
            token=token or secrets.token_urlsafe(32),
            token_generated=not token,
            port=int(env.get("BRIDGE_PORT", cls.port)),
            browser=browser,
            profile_dir=Path(profile_dir).expanduser(),
            headless=_flag(env, "BRIDGE_HEADLESS"),
            allow_private_networks=_flag(env, "BRIDGE_ALLOW_PRIVATE_NETWORKS"),
            max_sessions=int(env.get("BRIDGE_MAX_SESSIONS", cls.max_sessions)),
        )

    @property
    def channel(self) -> str | None:
        """Playwright's name for the installed browser to drive; None means its own Chromium."""
        return None if self.browser == "chromium" else self.browser


def _flag(env: Mapping[str, str], name: str) -> bool:
    return env.get(name, "").strip().lower() in {"1", "true", "yes"}
