import asyncio

import pytest

from browser_bridge.config import Settings
from browser_bridge.network_guard import PrivateNetworkGuard


@pytest.mark.parametrize(
    ("url", "public"),
    [
        ("https://8.8.8.8/", True),
        ("http://127.0.0.1:8000/", False),
        ("http://localhost/", False),
        ("http://10.1.2.3/", False),
        ("http://192.168.1.1/", False),
        ("http://172.16.0.1/", False),
        ("http://169.254.169.254/latest/meta-data/", False),
        ("http://[::1]/", False),
        ("http://[::ffff:127.0.0.1]/", False),
        ("http://[fe80::1]/", False),
        ("about:blank", False),
    ],
)
def test_network_guard(url: str, public: bool) -> None:
    assert asyncio.run(PrivateNetworkGuard().is_public(url)) is public


def test_generates_a_token_when_none_is_set() -> None:
    settings = Settings.from_env({})
    assert settings.token_generated
    assert len(settings.token) >= 32


def test_rejects_a_short_token() -> None:
    with pytest.raises(ValueError, match="at least"):
        Settings.from_env({"BRIDGE_TOKEN": "short"})


def test_reads_settings_from_env(tmp_path) -> None:
    settings = Settings.from_env(
        {
            "BRIDGE_TOKEN": "x" * 24,
            "BRIDGE_PORT": "9000",
            "BRIDGE_PROFILE_DIR": str(tmp_path),
            "BRIDGE_HEADLESS": "true",
            "BRIDGE_ALLOW_PRIVATE_NETWORKS": "1",
            "BRIDGE_MAX_SESSIONS": "3",
        }
    )
    assert (settings.token_generated, settings.port, settings.profile_dir) == (
        False,
        9000,
        tmp_path,
    )
    assert (settings.headless, settings.allow_private_networks, settings.max_sessions) == (
        True,
        True,
        3,
    )
