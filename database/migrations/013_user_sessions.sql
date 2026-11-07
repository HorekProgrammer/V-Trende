-- 013: сессии пользователей сайта.
-- После регистрации (а позже и входа) пользователь получает случайный токен в cookie
-- vtrende_session. В базе хранится только SHA-256 от токена: утечка таблицы не даёт
-- войти чужой сессией. Сессию можно отозвать, удалив строку.

CREATE TABLE user_sessions (
    token_hash TEXT PRIMARY KEY CHECK (token_hash ~ '^[0-9a-f]{64}$'),
    user_id    BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT ck_user_sessions_expiry CHECK (expires_at > created_at)
);

CREATE INDEX ix_user_sessions_user ON user_sessions (user_id);
-- Для периодической очистки истёкших сессий.
CREATE INDEX ix_user_sessions_expires ON user_sessions (expires_at);

-- Email хранится в нижнем регистре (backend/auth.py), поэтому LOWER(email) = email.
-- Пустой email запрещён и на уровне базы, не только в приложении.
ALTER TABLE users
    ADD CONSTRAINT ck_users_email_not_blank CHECK (length(btrim(email)) BETWEEN 3 AND 254);
