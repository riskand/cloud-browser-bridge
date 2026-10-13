"""Bridge settings, read once from environment variables."""

import os
import secrets
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

MIN_TOKEN_LENGTH = 24
DEFAULT_PROFILE_DIR = Path.home() / ".browser-bridge-profile"


@dataclass(frozen=True)
class Settings:
    token: str
    token_generated: bool = False
    port: int = 8765
    profile_dir: Path = DEFAULT_PROFILE_DIR
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
        return cls(
            token=token or secrets.token_urlsafe(32),
            token_generated=not token,
            port=int(env.get("BRIDGE_PORT", cls.port)),
            profile_dir=Path(env.get("BRIDGE_PROFILE_DIR", DEFAULT_PROFILE_DIR)).expanduser(),
            headless=_flag(env, "BRIDGE_HEADLESS"),
            allow_private_networks=_flag(env, "BRIDGE_ALLOW_PRIVATE_NETWORKS"),
            max_sessions=int(env.get("BRIDGE_MAX_SESSIONS", cls.max_sessions)),
        )


def _flag(env: Mapping[str, str], name: str) -> bool:
    return env.get(name, "").strip().lower() in {"1", "true", "yes"}
