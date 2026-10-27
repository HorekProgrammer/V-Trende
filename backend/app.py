"""Read-only FastAPI application serving trend data from PostgreSQL."""

from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware

from database.db import connect, settings

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
