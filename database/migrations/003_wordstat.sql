-- 003: частота поисковых запросов из Яндекс Wordstat.
-- Это не позиция в чарте, а общий для всех категорий показатель интереса:
-- по нему упорядочивается смешанная лента на главной и строится график интереса.

-- Фраза для Wordstat, заданная вручную. NULL — фраза формируется автоматически
-- (parser/common/search_query.py): «исполнитель название» для музыки,
-- «название фильм» для фильмов, название для игр и стримеров.
ALTER TABLE trends ADD COLUMN search_query TEXT
    CHECK (search_query IS NULL OR length(btrim(search_query)) BETWEEN 1 AND 400);

-- Одно значение на объект за неделю замера.
CREATE TABLE trend_search_stats (
    trend_id     BIGINT NOT NULL REFERENCES trends(id) ON DELETE CASCADE,
    week_start   DATE NOT NULL CHECK (EXTRACT(ISODOW FROM week_start) = 1),
    -- Фраза, по которой реально получено значение (на случай её изменения).
    query        TEXT NOT NULL,
    -- Число запросов в России за последние 30 дней на момент сбора.
    search_count INTEGER NOT NULL CHECK (search_count >= 0),
    collected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (trend_id, week_start)
);

CREATE INDEX ix_trend_search_stats_week ON trend_search_stats (week_start);
