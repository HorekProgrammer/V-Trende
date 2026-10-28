-- 005: итоговый рейтинг MVP: 85% сигналы источников + 15% Яндекс Wordstat.
-- Twitch использует собственные недельные метрики вместо одной позиции в чарте.

CREATE TABLE twitch_weekly_stats (
    trend_id          BIGINT NOT NULL REFERENCES trends(id) ON DELETE CASCADE,
    week_start        DATE NOT NULL CHECK (EXTRACT(ISODOW FROM week_start) = 1),
    total_followers   BIGINT NOT NULL CHECK (total_followers >= 0),
    hours_streamed    NUMERIC(12, 2) NOT NULL CHECK (hours_streamed >= 0),
    average_viewers   BIGINT NOT NULL CHECK (average_viewers >= 0),
    peak_viewers      BIGINT NOT NULL CHECK (peak_viewers >= 0),
    hours_watched     BIGINT NOT NULL CHECK (hours_watched >= 0),
    followers_gained  BIGINT NOT NULL CHECK (followers_gained >= 0),
    followers_per_hour NUMERIC(12, 3) NOT NULL CHECK (followers_per_hour >= 0),
    collected_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (trend_id, week_start)
);

-- Веса отражают относительную значимость российских чартов внутри категории.
-- При недоступности источника веса оставшихся источников нормализуются автоматически.
CREATE TABLE chart_weights (
    source TEXT NOT NULL,
    name   TEXT NOT NULL,
    weight NUMERIC(6, 5) NOT NULL CHECK (weight > 0 AND weight <= 1),
    PRIMARY KEY (source, name)
);

INSERT INTO chart_weights (source, name, weight) VALUES
    ('yandex_music', 'Чарт',                    0.25),
    ('vk',           'Чарт VK Музыки',         0.25),
    ('zvuk',         'Топ-100',                 0.15),
    ('apple_music',  'Топ-100 Россия',          0.15),
    ('shazam',       'Топ-200 Россия',          0.10),
    ('kion',         'Настоящий чарт',          0.10),
    ('steam',        'Most Played',              0.30),
    ('steam',        'Top Sellers',              0.25),
    ('epic',         'Most Played',              0.25),
    ('epic',         'Most Popular',             0.20),
    ('kinopoisk',    'Популярные фильмы',        0.65),
    ('kinopoisk',    'Кассовые сборы выходных',  0.35),
    ('twitch',       'Русскоязычные стримеры',   1.00);

DROP VIEW v_trend_history;
DROP VIEW v_main_feed;
DROP VIEW v_category_top_latest;
DROP VIEW v_category_top;
DROP MATERIALIZED VIEW mv_category_rank;
DROP VIEW v_category_weekly_rank;

-- Позиция нормализуется в диапазон 0..1 внутри фактически собранного чарта.
-- Затем чарты объединяются с учётом веса источника.
CREATE VIEW v_category_weekly_score AS
WITH position_rows AS (
    SELECT e.*,
           MAX(e.position) OVER (PARTITION BY e.chart_id, e.week_start) AS chart_size,
           COALESCE(w.weight, 1.0) AS chart_weight
    FROM v_chart_entries e
    LEFT JOIN chart_weights w ON w.source = e.source AND w.name = e.chart_name
),
chart_aggregates AS (
    SELECT week_start,
           category,
           trend_id,
           SUM(
               (CASE WHEN chart_size <= 1 THEN 1.0
                     ELSE 1.0 - (position - 1)::NUMERIC / (chart_size - 1)
                END) * chart_weight
           ) / SUM(chart_weight) AS position_score,
           AVG(position) AS avg_raw,
           COUNT(*) AS chart_count,
           MIN(position) AS best_position
    FROM position_rows
    GROUP BY week_start, category, trend_id
),
twitch_percentiles AS (
    SELECT s.*,
           PERCENT_RANK() OVER (PARTITION BY week_start ORDER BY hours_watched) AS p_hours_watched,
           PERCENT_RANK() OVER (PARTITION BY week_start ORDER BY average_viewers) AS p_average_viewers,
           PERCENT_RANK() OVER (PARTITION BY week_start ORDER BY peak_viewers) AS p_peak_viewers,
           PERCENT_RANK() OVER (PARTITION BY week_start ORDER BY followers_gained) AS p_followers_gained,
           PERCENT_RANK() OVER (PARTITION BY week_start ORDER BY followers_per_hour) AS p_followers_per_hour,
           PERCENT_RANK() OVER (PARTITION BY week_start ORDER BY hours_streamed) AS p_hours_streamed,
           PERCENT_RANK() OVER (PARTITION BY week_start ORDER BY total_followers) AS p_total_followers
    FROM twitch_weekly_stats s
),
twitch_scores AS (
    SELECT trend_id,
           week_start,
           p_hours_watched      * 0.30 +
           p_average_viewers    * 0.20 +
           p_peak_viewers       * 0.10 +
           p_followers_gained   * 0.20 +
           p_followers_per_hour * 0.10 +
           p_hours_streamed     * 0.05 +
           p_total_followers    * 0.05 AS twitch_score
    FROM twitch_percentiles
),
source_scores AS (
    SELECT a.*,
           CASE WHEN a.category = 'streamers'
                THEN COALESCE(t.twitch_score, a.position_score)
                ELSE a.position_score
           END AS source_score
    FROM chart_aggregates a
    LEFT JOIN twitch_scores t
           ON t.trend_id = a.trend_id AND t.week_start = a.week_start
),
wordstat_logs AS (
    SELECT t.category,
           s.trend_id,
           s.week_start,
           LN(1 + s.search_count::NUMERIC) AS value
    FROM trend_search_stats s
    JOIN trends t ON t.id = s.trend_id
),
wordstat_bounds AS (
    SELECT w.*,
           MIN(value) OVER (PARTITION BY category, week_start) AS min_value,
           MAX(value) OVER (PARTITION BY category, week_start) AS max_value
    FROM wordstat_logs w
),
wordstat_scores AS (
    SELECT trend_id,
           week_start,
           CASE WHEN max_value = min_value THEN 1.0
                ELSE (value - min_value) / (max_value - min_value)
           END AS wordstat_score
    FROM wordstat_bounds
),
collected AS (
    SELECT r.week_start, c.category, COUNT(*) AS charts_collected
    FROM chart_runs r
    JOIN charts c ON c.id = r.chart_id
    WHERE r.status = 'success'
    GROUP BY r.week_start, c.category
),
scored AS (
    SELECT s.*,
           col.charts_collected,
           cs.top_limit,
           COALESCE(w.wordstat_score, 0.0) AS wordstat_score,
           s.source_score * 0.85 + COALESCE(w.wordstat_score, 0.0) * 0.15 AS final_score
    FROM source_scores s
    JOIN collected col USING (week_start, category)
    JOIN category_settings cs ON cs.category = s.category
    LEFT JOIN wordstat_scores w
           ON w.trend_id = s.trend_id AND w.week_start = s.week_start
    WHERE s.chart_count >= LEAST(cs.min_charts, col.charts_collected)
),
ranked AS (
    SELECT s.*,
           ROW_NUMBER() OVER (
               PARTITION BY week_start, category
               ORDER BY final_score DESC, chart_count DESC, best_position, trend_id
           ) AS rank
    FROM scored s
)
SELECT week_start,
       category,
       trend_id,
       rank::INTEGER AS rank,
       ROUND((final_score * 100)::NUMERIC, 2) AS score,
       ROUND((source_score * 100)::NUMERIC, 2) AS source_score,
       ROUND((wordstat_score * 100)::NUMERIC, 2) AS wordstat_score,
       ROUND(avg_raw, 2) AS avg_position,
       chart_count::INTEGER AS chart_count,
       charts_collected::INTEGER AS charts_collected,
       best_position::INTEGER AS best_position
FROM ranked
WHERE rank <= top_limit;

CREATE MATERIALIZED VIEW mv_category_rank AS
WITH first_seen AS (
    SELECT trend_id, MIN(week_start) AS first_seen_week
    FROM v_chart_entries
    GROUP BY trend_id
),
history AS (
    SELECT w.*,
           LAG(w.week_start) OVER previous AS prev_week,
           LAG(w.rank) OVER previous AS prev_rank_any,
           MIN(w.rank) OVER cumulative AS peak_rank,
           COUNT(*) OVER cumulative AS weeks_in_top
    FROM v_category_weekly_score w
    WINDOW previous AS (PARTITION BY w.category, w.trend_id ORDER BY w.week_start),
           cumulative AS (PARTITION BY w.category, w.trend_id ORDER BY w.week_start
                          ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
)
SELECT h.week_start,
       h.category,
       h.trend_id,
       h.rank,
       h.score,
       h.source_score,
       h.wordstat_score,
       h.avg_position,
       h.chart_count,
       h.charts_collected,
       h.best_position,
       CASE WHEN h.prev_week = h.week_start - 7 THEN h.prev_rank_any END AS prev_rank,
       h.peak_rank,
       h.weeks_in_top::INTEGER AS weeks_in_top,
       fs.first_seen_week
FROM history h
JOIN first_seen fs ON fs.trend_id = h.trend_id;

CREATE UNIQUE INDEX uq_mv_category_rank ON mv_category_rank (week_start, category, trend_id);
CREATE INDEX ix_mv_category_rank_top ON mv_category_rank (category, week_start, rank);
CREATE INDEX ix_mv_category_rank_trend ON mv_category_rank (trend_id, week_start);

CREATE VIEW v_category_top AS
SELECT r.week_start,
       r.category,
       r.rank,
       r.score,
       r.source_score,
       r.wordstat_score,
       r.trend_id,
       t.title,
       t.subtitle,
       g.name AS genre,
       r.avg_position,
       r.chart_count,
       r.charts_collected,
       r.best_position,
       r.prev_rank,
       r.prev_rank - r.rank AS rank_change,
       r.peak_rank,
       r.weeks_in_top,
       r.first_seen_week,
       r.first_seen_week = r.week_start AS is_new,
       ss.search_count,
       ps.search_count AS prev_search_count
FROM mv_category_rank r
JOIN trends t ON t.id = r.trend_id
LEFT JOIN genres g ON g.id = t.genre_id
LEFT JOIN trend_search_stats ss
       ON ss.trend_id = r.trend_id AND ss.week_start = r.week_start
LEFT JOIN trend_search_stats ps
       ON ps.trend_id = r.trend_id AND ps.week_start = r.week_start - 7;

CREATE VIEW v_category_top_latest AS
SELECT t.*
FROM v_category_top t
JOIN v_latest_weeks l ON l.category = t.category AND l.week_start = t.week_start;

CREATE VIEW v_main_feed AS
SELECT ROW_NUMBER() OVER (
           ORDER BY l.score DESC, l.search_count DESC NULLS LAST, l.rank, l.category, l.trend_id
       )::INTEGER AS feed_rank,
       l.*
FROM v_category_top_latest l;

CREATE VIEW v_trend_history AS
WITH weeks AS (
    SELECT trend_id, week_start FROM v_chart_entries
    UNION
    SELECT trend_id, week_start FROM trend_search_stats
)
SELECT wk.trend_id,
       wk.week_start,
       w.rank AS category_rank,
       w.score,
       w.source_score,
       w.wordstat_score,
       w.avg_position,
       w.chart_count,
       ss.search_count
FROM weeks wk
LEFT JOIN mv_category_rank w
       ON w.trend_id = wk.trend_id AND w.week_start = wk.week_start
LEFT JOIN trend_search_stats ss
       ON ss.trend_id = wk.trend_id AND ss.week_start = wk.week_start;
