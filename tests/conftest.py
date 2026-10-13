import threading
from collections.abc import Callable, Iterator
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from browser_bridge.api import create_app
from browser_bridge.config import Settings

TOKEN = "t" * 32
AUTH = {"Authorization": f"Bearer {TOKEN}"}

PAGES = {
    "index.html": """<html><head><title>Home</title></head><body>
        <h1>Home page</h1><a href="/next.html">Next page</a>
        <form action="/next.html"><input id="q" name="q"><button id="go">Go</button></form>
        </body></html>""",
    "next.html": "<html><head><title>Next</title></head><body><p>Second page</p></body></html>",
    "other.html": "<html><head><title>Other</title></head><body><p>Other page</p></body></html>",
}


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args: object) -> None:
        pass


@pytest.fixture(scope="session")
def site(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    """A local web server with the test pages; yields its base URL."""
    root = tmp_path_factory.mktemp("site")
    for name, html in PAGES.items():
        (root / name).write_text(html)
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(root)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


@pytest.fixture
def make_client(tmp_path: Path) -> Iterator[Callable[..., TestClient]]:
    """Starts a bridge (headless, fresh profile) with the given setting overrides."""
    clients: list[TestClient] = []

    def start(**overrides: object) -> TestClient:
        defaults = {
            "token": TOKEN,
            "profile_dir": tmp_path / f"profile-{len(clients)}",
            "browser": "chromium",
            "headless": True,
            "allow_private_networks": True,
            "action_timeout_ms": 1_000,
        }
        settings = Settings(**{**defaults, **overrides})
        client = TestClient(create_app(settings), headers=AUTH)
        client.__enter__()
        clients.append(client)
        return client

    yield start
    for client in clients:
        client.__exit__(None, None, None)


@pytest.fixture
def client(make_client: Callable[..., TestClient]) -> TestClient:
    return make_client()
