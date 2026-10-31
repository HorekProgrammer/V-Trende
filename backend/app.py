"""FastAPI application serving trends and accepting parser payloads."""

import hmac
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware

from database.db import connect, settings
from database.load_outbox import PayloadError, load_payload, refresh_rankings

from . import repository

app = FastAPI(title="V-Trende API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in (settings().get("CORS_ORIGINS") or "http://localhost:5173").split(",")
        if origin.strip()
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def database():
    with connect() as conn:
        yield conn


Db = Annotated[object, Depends(database)]


def require_internal_token(
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    expected = (settings().get("INTERNAL_API_TOKEN") or "").strip()
    scheme, _, supplied = (authorization or "").partition(" ")
    if (
        not expected
        or scheme.lower() != "bearer"
        or not supplied
        or not hmac.compare_digest(supplied, expected)
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Неверный внутренний токен.")


InternalAuth = Annotated[None, Depends(require_internal_token)]


def ingest_payload(payload: dict, conn, expected_type: str) -> dict:
    actual_type = payload.get("type", "chart")
    if actual_type != expected_type:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Неверный тип пакета.")
    try:
        with conn.transaction():
            message = load_payload(conn, payload)
    except PayloadError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from None
    return {"message": message}


@app.get("/api/v1/health")
def health():
    return {"status": "ok"}


@app.get("/api/v1/categories")
def get_categories(conn: Db):
    return repository.categories(conn)


@app.get("/api/v1/feed")
def get_feed(conn: Db):
    return repository.feed(conn)


@app.get("/api/v1/trends")
def get_trends(
    conn: Db,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    return repository.main_trends(conn, limit, offset)


@app.get("/api/v1/categories/{category}/trends")
def get_category_trends(
    category: str,
    conn: Db,
    sort: str = Query("popular", pattern="^(popular|new|rising)$"),
    genre: list[str] = Query(default=[]),
    limit: int = Query(100, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    if category not in repository.CATEGORY_LABELS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Категория не найдена.")
    return repository.category_trends(conn, category, sort, genre, limit, offset)


@app.get("/api/v1/trends/category/{category}")
def get_category_trends_legacy(
    category: str,
    conn: Db,
    sort_by: str = Query("popular", pattern="^(popular|new|rising)$"),
    genre: list[str] = Query(default=[]),
    limit: int = Query(100, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """Контракт из архитектурной документации; основной URL — /categories/.../trends."""
    if category not in repository.CATEGORY_LABELS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Категория не найдена.")
    return repository.category_trends(conn, category, sort_by, genre, limit, offset)


@app.get("/api/v1/trends/{trend_id}")
def get_trend(trend_id: int, conn: Db):
    item = repository.trend(conn, trend_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Тренд не найден.")
    return item


@app.get("/api/v1/trends/{trend_id}/history")
def get_trend_history(trend_id: int, conn: Db):
    history = repository.trend_history(conn, trend_id)
    if history is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Тренд не найден.")
    return history


@app.post("/api/v1/internal/update-trends")
def update_trends(payload: dict, conn: Db, _auth: InternalAuth):
    return ingest_payload(payload, conn, "chart")


@app.post("/api/v1/internal/update-search-stats")
def update_search_stats(payload: dict, conn: Db, _auth: InternalAuth):
    # Автоматический воскресный сбор сохраняет данные заранее, но публикует их
    # отдельной задачей ровно в понедельник 00:00 МСК.
    publish = payload.get("publish", True)
    if type(publish) is not bool:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Поле publish должно быть boolean.")
    result = ingest_payload(payload, conn, "search_stats")
    if publish:
        refresh_rankings(conn)
    result["rankingsRefreshed"] = publish
    return result


@app.post("/api/v1/internal/update-game-audience-stats")
def update_game_audience_stats(payload: dict, conn: Db, _auth: InternalAuth):
    publish = payload.get("publish", False)
    if type(publish) is not bool:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Поле publish должно быть boolean.")
    result = ingest_payload(payload, conn, "game_audience_stats")
    if publish:
        refresh_rankings(conn)
    result["rankingsRefreshed"] = publish
    return result


@app.post("/api/v1/internal/publish-rankings")
def publish_rankings(conn: Db, _auth: InternalAuth):
    refresh_rankings(conn)
    return {"message": "Рейтинг опубликован.", "rankingsRefreshed": True}
