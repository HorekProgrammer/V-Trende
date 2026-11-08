"""FastAPI application serving trends and accepting parser payloads."""

import hmac
from datetime import date
from typing import Annotated

from fastapi import Cookie, Depends, FastAPI, Header, HTTPException, Query, Response, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database.db import connect, settings
from database.load_outbox import PayloadError, load_payload, refresh_rankings

from . import auth, repository

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


class RegisterRequest(BaseModel):
    email: str
    password: str


def _cookie_secure() -> bool:
    # На локальной разработке сайт работает по http, там флаг Secure ставить нельзя.
    return (settings().get("SESSION_COOKIE_SECURE") or "").strip().lower() in {"1", "true", "yes"}


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        auth.SESSION_COOKIE,
        token,
        max_age=int(auth.SESSION_TTL.total_seconds()),
        httponly=True,       # недоступна JavaScript: XSS не украдёт сессию
        samesite="lax",      # не отправляется с чужих сайтов при POST-запросах
        secure=_cookie_secure(),
        path="/",
    )


@app.post("/api/v1/auth/register", status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, response: Response, conn: Db):
    """Регистрация по email и паролю. Сразу выполняет вход: ставит cookie сессии.

    Ошибки: 422 — некорректные поля, 409 — email уже занят.
    В обоих случаях detail = {"message": ..., "fields": {"email"|"password": ...}}.
    """
    errors = auth.validate_registration(body.email, body.password)
    if errors:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            {"message": "Проверьте поля формы.", "fields": errors},
        )
    try:
        user, token = auth.register(conn, body.email, body.password)
    except auth.EmailTaken:
        message = "Пользователь с таким email уже зарегистрирован"
        raise HTTPException(
            status.HTTP_409_CONFLICT, {"message": message, "fields": {"email": message}}
        ) from None
    _set_session_cookie(response, token)
    return {"user": auth.public_user(user)}

class LoginRequest(BaseModel):
    email: str
    password: str


@app.post("/api/v1/auth/login")
def login(body: LoginRequest, response: Response, conn: Db):
    """Вход по email и паролю. Ставит cookie сессии."""
    try:
        user, token = auth.login(conn, body.email, body.password)
    except auth.InvalidCredentials:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            {"message": "Неверный email или пароль"},
        ) from None

    _set_session_cookie(response, token)
    return {"user": auth.public_user(user)}

@app.get("/api/v1/auth/me")
def me(
    conn: Db,
    vtrende_session: Annotated[str | None, Cookie()] = None,
):
    """Текущий пользователь по cookie сессии; 401, если вход не выполнен."""
    user = auth.session_user(conn, vtrende_session)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Вход не выполнен.")
    return {"user": auth.public_user(user)}


@app.get("/api/v1/health")
def health():
    return {"status": "ok"}


def require_week(conn, week: date | None) -> None:
    if week is not None and not repository.week_exists(conn, week):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Неделя не найдена.")


@app.get("/api/v1/weeks")
def get_weeks(conn: Db):
    """Доступные недели, от новой к старой: для переключателя на сайте."""
    return repository.weeks(conn)


@app.get("/api/v1/categories")
def get_categories(conn: Db):
    return repository.categories(conn)


@app.get("/api/v1/feed")
def get_feed(conn: Db, week: date | None = Query(None)):
    require_week(conn, week)
    return repository.feed(conn, week)


@app.get("/api/v1/trends")
def get_trends(
    conn: Db,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    week: date | None = Query(None),
):
    require_week(conn, week)
    return repository.main_trends(conn, limit, offset, week)


@app.get("/api/v1/categories/{category}/trends")
def get_category_trends(
    category: str,
    conn: Db,
    sort: str = Query("popular", pattern="^(popular|new|rising)$"),
    genre: list[str] = Query(default=[]),
    limit: int = Query(100, ge=1, le=100),
    offset: int = Query(0, ge=0),
    week: date | None = Query(None),
):
    if category not in repository.CATEGORY_LABELS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Категория не найдена.")
    require_week(conn, week)
    return repository.category_trends(conn, category, sort, genre, limit, offset, week)


@app.get("/api/v1/trends/category/{category}")
def get_category_trends_legacy(
    category: str,
    conn: Db,
    sort_by: str = Query("popular", pattern="^(popular|new|rising)$"),
    genre: list[str] = Query(default=[]),
    limit: int = Query(100, ge=1, le=100),
    offset: int = Query(0, ge=0),
    week: date | None = Query(None),
):
    """Контракт из архитектурной документации; основной URL — /categories/.../trends."""
    if category not in repository.CATEGORY_LABELS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Категория не найдена.")
    require_week(conn, week)
    return repository.category_trends(conn, category, sort_by, genre, limit, offset, week)


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


@app.post("/api/v1/auth/logout")
def logout(
    conn: Db,
    response: Response,
    vtrende_session: Annotated[str | None, Cookie()] = None,
):
    """Удаляет сессию из базы и сбрасывает cookie."""
    if vtrende_session:
        conn.execute(
            "DELETE FROM user_sessions WHERE token_hash = %s",
            (auth._token_hash(vtrende_session),),
        )
    response.delete_cookie(auth.SESSION_COOKIE, path="/")
    return {"message": "Выход выполнен."}