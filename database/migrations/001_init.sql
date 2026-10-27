-- 001: исходная схема «В-Тренде» (бывший database/schema.sql).
-- Хранятся только позиции объектов в чартах и недельные замеры.
-- Платформенные показатели (прослушивания, продажи, зрители и т. п.) не хранятся.
-- IF NOT EXISTS оставлен, чтобы базу, созданную из schema.sql, можно было
-- отметить применённой: python -m database.migrate --baseline 001

-- Пользователи сайта.
CREATE TABLE IF NOT EXISTS users (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email         TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Email уникален без учёта регистра: Mark@mail.ru и mark@mail.ru — один пользователь.
CREATE UNIQUE INDEX IF NOT EXISTS uq_users_email_lower
    ON users (LOWER(email));

-- Объекты трендов: песня, игра, фильм или стример.
-- Один объект может присутствовать в чартах нескольких источников.
CREATE TABLE IF NOT EXISTS trends (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    category   TEXT NOT NULL
               CHECK (category IN ('games', 'music', 'movies', 'streamers')),
    title      TEXT NOT NULL,
    -- Подзаголовок карточки: исполнитель для музыки, год для фильма и т. п.
    subtitle   TEXT,
    -- Жанр для фильтра на странице категории; заполняется, если известен.
    genre      TEXT,
    -- Ключ сопоставления одного объекта между источниками.
    -- Формируется при загрузке (parser/common/normalize.py):
    -- «исполнитель|название» для музыки, «название» для остального.
    match_key  TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_trends_category_match_key UNIQUE (category, match_key)
);

-- Чарты источников, например «Shazam — Топ-200 Россия» или «Steam — Top Sellers».
-- Все чарты российские, поэтому регион не хранится.
CREATE TABLE IF NOT EXISTS charts (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source     TEXT NOT NULL,
    name       TEXT NOT NULL,
    category   TEXT NOT NULL
               CHECK (category IN ('games', 'music', 'movies', 'streamers')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_charts_source_name UNIQUE (source, name)
);

-- Еженедельные запуски сбора чарта.
-- Позволяют отличить «объект не попал в чарт» от «чарт не удалось собрать».
CREATE TABLE IF NOT EXISTS chart_runs (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    chart_id    BIGINT NOT NULL REFERENCES charts(id) ON DELETE CASCADE,
    -- Понедельник недели, к которой относится замер. Именно период,
    -- а не время запуска: повторный запуск в ту же неделю попадает в ту же строку.
    week_start  DATE NOT NULL CHECK (EXTRACT(ISODOW FROM week_start) = 1),
    status      TEXT NOT NULL DEFAULT 'running'
                CHECK (status IN ('running', 'success', 'failed')),
    started_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    error       TEXT,
    CONSTRAINT uq_chart_runs_chart_week UNIQUE (chart_id, week_start),
    CONSTRAINT ck_chart_runs_finished
        CHECK (status = 'running' OR finished_at IS NOT NULL)
);

-- Идентификаторы и ссылки объекта на конкретных платформах.
CREATE TABLE IF NOT EXISTS trend_source_items (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    trend_id    BIGINT NOT NULL REFERENCES trends(id) ON DELETE CASCADE,
    source      TEXT NOT NULL,
    external_id TEXT,
    url         TEXT,
    CONSTRAINT ck_trend_source_item_has_identity
        CHECK (external_id IS NOT NULL OR url IS NOT NULL)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_trend_source_items_external_id
    ON trend_source_items (source, external_id)
    WHERE external_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_trend_source_items_url
    ON trend_source_items (source, url)
    WHERE external_id IS NULL AND url IS NOT NULL;

CREATE INDEX IF NOT EXISTS ix_trend_source_items_trend
    ON trend_source_items (trend_id);

-- Позиции объектов в конкретном запуске сбора чарта.
-- Чарт и неделя берутся из chart_runs.
CREATE TABLE IF NOT EXISTS trend_history (
    id       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id   BIGINT NOT NULL REFERENCES chart_runs(id) ON DELETE CASCADE,
    trend_id BIGINT NOT NULL REFERENCES trends(id) ON DELETE CASCADE,
    -- Все чарты обрезаются до топ-100, чтобы позиции были сопоставимы.
    position SMALLINT NOT NULL CHECK (position BETWEEN 1 AND 100),
    -- Один объект — одна позиция в замере; одна позиция — один объект.
    CONSTRAINT uq_trend_history_run_trend UNIQUE (run_id, trend_id),
    CONSTRAINT uq_trend_history_run_position UNIQUE (run_id, position)
);

-- История одного тренда для графика на странице тренда.
CREATE INDEX IF NOT EXISTS ix_trend_history_trend
    ON trend_history (trend_id);

-- Топ чарта за неделю покрывает уникальный индекс (run_id, position),
-- поиск последнего запуска чарта — уникальный индекс (chart_id, week_start).
