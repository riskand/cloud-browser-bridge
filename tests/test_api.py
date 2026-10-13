from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from browser_bridge.api import SESSION_HEADER


def session(name: str) -> dict[str, str]:
    return {SESSION_HEADER: name}


def test_rejects_missing_and_wrong_token(client: TestClient) -> None:
    assert client.get("/text", headers={"Authorization": ""}).status_code == 401
    assert client.get("/text", headers={"Authorization": "Bearer wrong"}).status_code == 401


def test_unauthenticated_requests_open_no_tabs(client: TestClient) -> None:
    client.get("/text", headers={"Authorization": "", **session("intruder")})
    assert "intruder" not in client.get("/sessions").json()["sessions"]


def test_exposes_no_api_docs(client: TestClient) -> None:
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 404


def test_browses_reads_fills_and_clicks(client: TestClient, site: str) -> None:
    opened = client.post("/goto", json={"url": f"{site}/index.html"}).json()
    assert opened == {"url": f"{site}/index.html", "title": "Home", "status": 200}

    assert "Home page" in client.get("/text").json()["text"]
    assert client.get("/links").json()["links"] == [
        {"text": "Next page", "href": f"{site}/next.html"}
    ]

    client.post("/fill", json={"selector": "#q", "value": "python"}).raise_for_status()
    clicked = client.post("/click", json={"selector": "#go"}).json()
    assert clicked == {"url": f"{site}/next.html?q=python", "title": "Next"}

    assert client.post("/back").json()["title"] == "Home"
    assert client.post("/press", json={"key": "End"}).status_code == 200


def test_screenshot_is_png(client: TestClient, site: str) -> None:
    client.post("/goto", json={"url": f"{site}/index.html"})
    response = client.get("/screenshot")
    assert response.headers["content-type"] == "image/png"
    assert response.content.startswith(b"\x89PNG")


def test_only_http_urls_are_accepted(client: TestClient) -> None:
    for url in ("file:///etc/passwd", "chrome://settings", "javascript:alert(1)"):
        assert client.post("/goto", json={"url": url}).status_code == 422


def test_browser_failure_is_a_clean_422(client: TestClient, site: str) -> None:
    client.post("/goto", json={"url": f"{site}/index.html"})
    response = client.post("/click", json={"selector": "#missing"})
    assert response.status_code == 422
    assert "Timeout" in response.json()["error"]


def test_sessions_get_separate_tabs(client: TestClient, site: str) -> None:
    client.post("/goto", json={"url": f"{site}/next.html"}, headers=session("a"))
    client.post("/goto", json={"url": f"{site}/other.html"}, headers=session("b"))

    assert client.get("/text", headers=session("a")).json()["title"] == "Next"
    assert client.get("/text", headers=session("b")).json()["title"] == "Other"
    assert set(client.get("/sessions").json()["sessions"]) == {"default", "a", "b"}

    assert client.request("DELETE", "/session", headers=session("b")).json()["closed"] is True
    assert set(client.get("/sessions").json()["sessions"]) == {"default", "a"}


def test_rejects_invalid_session_name(client: TestClient) -> None:
    assert client.get("/text", headers=session("../etc")).status_code == 400


def test_limits_open_sessions(make_client: Callable[..., TestClient], site: str) -> None:
    client = make_client(max_sessions=2)
    page = {"url": f"{site}/index.html"}
    assert client.post("/goto", json=page, headers=session("a")).status_code == 200  # + default
    assert client.post("/goto", json=page, headers=session("b")).status_code == 429

    client.request("DELETE", "/session", headers=session("a"))
    assert client.post("/goto", json=page, headers=session("b")).status_code == 200


def test_blocks_private_networks_by_default(
    make_client: Callable[..., TestClient], site: str
) -> None:
    client = make_client(allow_private_networks=False)
    response = client.post("/goto", json={"url": f"{site}/index.html"})
    assert response.status_code == 422
    assert "ERR_BLOCKED_BY_CLIENT" in response.json()["error"]


def test_parallel_sessions_never_see_each_others_pages(client: TestClient, site: str) -> None:
    def browse(name: str, page: str, title: str) -> list[str]:
        seen = []
        for _ in range(5):
            client.post("/goto", json={"url": f"{site}/{page}"}, headers=session(name))
            seen.append(client.get("/text", headers=session(name)).json()["title"])
        return [t for t in seen if t != title]

    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(browse, "a", "next.html", "Next")
        b = pool.submit(browse, "b", "other.html", "Other")
        assert (a.result(), b.result()) == ([], [])
