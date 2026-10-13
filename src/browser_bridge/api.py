"""HTTP API: a narrow, token-protected set of browser actions."""

import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Page
from pydantic import BaseModel, HttpUrl

from . import browser
from .config import Settings

MAX_TEXT_CHARS = 200_000
SESSION_HEADER = "X-Bridge-Session"


class Goto(BaseModel):
    url: HttpUrl


class Target(BaseModel):
    selector: str


class Fill(Target):
    value: str


class Key(BaseModel):
    key: str


def require_token(request: Request, authorization: Annotated[str, Header()] = "") -> None:
    expected = f"Bearer {request.app.state.settings.token}"
    if not secrets.compare_digest(authorization.encode(), expected.encode()):
        raise HTTPException(status_code=401, detail="missing or wrong bearer token")


def session_id(x_bridge_session: Annotated[str, Header()] = browser.DEFAULT_SESSION) -> str:
    if not browser.SESSION_ID.fullmatch(x_bridge_session):
        raise HTTPException(
            status_code=400, detail=f"{SESSION_HEADER} must match {browser.SESSION_ID.pattern}"
        )
    return x_bridge_session


SessionId = Annotated[str, Depends(session_id)]


async def session_page(request: Request, sid: SessionId) -> AsyncIterator[Page]:
    async with request.app.state.tabs.use(sid) as page:
        yield page


SessionPage = Annotated[Page, Depends(session_page)]


async def location(page: Page) -> dict:
    return {"url": page.url, "title": await page.title()}


router = APIRouter()


@router.post("/goto")
async def goto(body: Goto, page: SessionPage) -> dict:
    response = await page.goto(str(body.url), wait_until="domcontentloaded")
    return {**await location(page), "status": response.status if response else None}


@router.get("/text")
async def text(page: SessionPage) -> dict:
    content = await page.inner_text("body")
    return {
        **await location(page),
        "text": content[:MAX_TEXT_CHARS],
        "truncated": len(content) > MAX_TEXT_CHARS,
    }


@router.get("/links")
async def links(page: SessionPage) -> dict:
    found = await page.eval_on_selector_all(
        "a[href]", "els => els.map(a => ({text: a.innerText.trim().slice(0, 200), href: a.href}))"
    )
    return {**await location(page), "links": found}


@router.post("/click")
async def click(body: Target, page: SessionPage) -> dict:
    await page.click(body.selector)
    return await location(page)


@router.post("/fill")
async def fill(body: Fill, page: SessionPage) -> dict:
    await page.fill(body.selector, body.value)
    return await location(page)


@router.post("/press")
async def press(body: Key, page: SessionPage) -> dict:
    await page.keyboard.press(body.key)
    return await location(page)


@router.post("/back")
async def back(page: SessionPage) -> dict:
    await page.go_back()
    return await location(page)


@router.get("/screenshot")
async def screenshot(page: SessionPage, full_page: Annotated[bool, Query()] = False) -> Response:
    return Response(await page.screenshot(full_page=full_page), media_type="image/png")


@router.get("/sessions")
async def sessions(request: Request) -> dict:
    return {"sessions": request.app.state.tabs.open_sessions()}


@router.delete("/session")
async def close_session(request: Request, sid: SessionId) -> dict:
    return {"session": sid, "closed": await request.app.state.tabs.close(sid)}


def create_app(settings: Settings) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with browser.launch(settings) as tabs:
            app.state.tabs = tabs
            yield

    app = FastAPI(
        title="cloud-browser-bridge",
        lifespan=lifespan,
        dependencies=[Depends(require_token)],
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.settings = settings
    app.include_router(router)

    @app.exception_handler(PlaywrightError)
    async def playwright_error(_: Request, exc: PlaywrightError) -> JSONResponse:
        return JSONResponse({"error": str(exc).splitlines()[0]}, status_code=422)

    @app.exception_handler(browser.SessionLimitReached)
    async def session_limit(_: Request, exc: browser.SessionLimitReached) -> JSONResponse:
        return JSONResponse({"error": str(exc)}, status_code=429)

    return app
