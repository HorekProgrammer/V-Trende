"""Регистрация и сессии пользователей. Без FastAPI: маршруты — в backend/app.py.

Пароль хранится только в виде хэша scrypt (стандартная библиотека Python,
устойчив к перебору на видеокартах за счёт затрат памяти). Сессия — случайный
токен в cookie; в базе лежит его SHA-256 (миграция 013_user_sessions.sql).
"""

import base64
import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta, timezone

# Те же правила, что и в frontend/src/utils/validation.js, чтобы сообщения совпадали.
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
EMAIL_MAX_LENGTH = 254
PASSWORD_MIN_LENGTH = 8
# Верхняя граница защищает от «хэширования мегабайтов» одним запросом.
PASSWORD_MAX_LENGTH = 128

# Параметры scrypt: ~60 мс и 16 МБ памяти на хэш (лимит README — 500 мс на регистрацию).
SCRYPT_N = 2 ** 14
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_DKLEN = 32
SALT_BYTES = 16

SESSION_COOKIE = "vtrende_session"
SESSION_TTL = timedelta(days=30)


class EmailTaken(Exception):
    """Пользователь с таким email уже есть."""


def normalize_email(value: str) -> str:
    """Email без пробелов по краям и в нижнем регистре: Mark@Mail.ru == mark@mail.ru."""
    return value.strip().lower()


def validate_registration(email: str, password: str) -> dict[str, str]:
    """Ошибки по полям; пустой словарь — данные корректны."""
    errors = {}
    email = normalize_email(email)
    if not email:
        errors["email"] = "Введите email"
    elif len(email) > EMAIL_MAX_LENGTH or not EMAIL_RE.match(email):
        errors["email"] = "Некорректный email"

    if not password:
        errors["password"] = "Введите пароль"
    elif len(password) < PASSWORD_MIN_LENGTH:
        errors["password"] = f"Минимум {PASSWORD_MIN_LENGTH} символов"
    elif len(password) > PASSWORD_MAX_LENGTH:
        errors["password"] = f"Максимум {PASSWORD_MAX_LENGTH} символов"
    return errors


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def hash_password(password: str) -> str:
    """Строка вида scrypt$N$r$p$соль$хэш: параметры хранятся вместе с хэшем,
    поэтому их можно усилить позже, не ломая старые пароли."""
    salt = secrets.token_bytes(SALT_BYTES)
    digest = hashlib.scrypt(
        password.encode("utf-8"), salt=salt,
        n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=SCRYPT_DKLEN,
    )
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored: str) -> bool:
    """Проверка пароля для будущего входа (/auth/login). Сравнение — за постоянное время."""
    try:
        scheme, n, r, p, salt, digest = stored.split("$")
        if scheme != "scrypt":
            return False
        expected = base64.b64decode(digest)
        actual = hashlib.scrypt(
            password.encode("utf-8"), salt=base64.b64decode(salt),
            n=int(n), r=int(r), p=int(p), dklen=len(expected),
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


def public_user(record: dict) -> dict:
    """То, что можно отдать фронтенду: без хэша пароля."""
    created = record["created_at"]
    return {
        "id": record["id"],
        "email": record["email"],
        "createdAt": created.isoformat() if hasattr(created, "isoformat") else created,
    }


def create_user(conn, email: str, password: str) -> dict:
    """Создаёт пользователя. Вызывать внутри транзакции; данные уже проверены."""
    row = conn.execute(
        """
        INSERT INTO users (email, password_hash) VALUES (%s, %s)
        ON CONFLICT DO NOTHING
        RETURNING id, email, created_at
        """,
        (normalize_email(email), hash_password(password)),
    ).fetchone()
    if row is None:
        # Сработал уникальный индекс uq_users_email_lower.
        raise EmailTaken
    return {"id": row[0], "email": row[1], "created_at": row[2]}


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def create_session(conn, user_id: int, *, now: datetime | None = None) -> str:
    """Новая сессия; возвращает токен для cookie (в базу попадает только его хэш)."""
    token = secrets.token_urlsafe(32)
    now = now or datetime.now(timezone.utc)
    conn.execute(
        "INSERT INTO user_sessions (token_hash, user_id, created_at, expires_at) VALUES (%s, %s, %s, %s)",
        (_token_hash(token), user_id, now, now + SESSION_TTL),
    )
    return token


def session_user(conn, token: str | None) -> dict | None:
    """Пользователь действующей сессии или None (нет токена, неверный, истёк)."""
    if not token or len(token) > 200:
        return None
    try:
        token_hash = _token_hash(token)
    except UnicodeEncodeError:
        return None
    row = conn.execute(
        """
        SELECT u.id, u.email, u.created_at
        FROM user_sessions s
        JOIN users u ON u.id = s.user_id
        WHERE s.token_hash = %s AND s.expires_at > NOW()
        """,
        (token_hash,),
    ).fetchone()
    if row is None:
        return None
    return {"id": row[0], "email": row[1], "created_at": row[2]}


def register(conn, email: str, password: str) -> tuple[dict, str]:
    """Пользователь и сессия в одной транзакции: не бывает аккаунта без входа и наоборот."""
    with conn.transaction():
        user = create_user(conn, email, password)
        token = create_session(conn, user["id"])
    return user, token
