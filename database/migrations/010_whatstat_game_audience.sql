-- Weekly Russian-language Twitch audience for games. Whatstat replaces
-- Wordstat only in the games ranking; API-facing score columns stay unchanged.
UPDATE category_settings
SET min_charts = 1
WHERE category = 'games';

CREATE TABLE game_audience_stats (
    trend_id           BIGINT NOT NULL REFERENCES trends(id) ON DELETE CASCADE,
    week_start         DATE NOT NULL CHECK (EXTRACT(ISODOW FROM week_start) = 1),
    source_title       TEXT NOT NULL,
    source_category_id TEXT NOT NULL,
    source_url         TEXT NOT NULL,
    position           INTEGER NOT NULL CHECK (position > 0),
    average_viewers    BIGINT NOT NULL CHECK (average_viewers >= 0),
    collected_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (trend_id, week_start),
    UNIQUE (source_category_id, week_start)
);

CREATE INDEX ix_game_audience_stats_week ON game_audience_stats (week_start);

CREATE OR REPLACE VIEW v_category_weekly_score AS
WITH position_rows AS (
    SELECT e.*,
           MAX(e.position) OVER (PARTITION BY e.chart_id, e.week_start) AS chart_size,
           COALESCE(w.weight, 1.0) AS chart_weight
    FROM v_chart_entries e
    LEFT JOIN chart_weights w ON w.source = e.source AND w.name = e.chart_name
),
normalized_positions AS (
    SELECT p.*,
           CASE WHEN chart_size <= 1 THEN 1.0
                ELSE 1.0 - (position - 1)::NUMERIC / (chart_size - 1)
           END AS normalized_position
    FROM position_rows p
),
chart_aggregates AS (
    SELECT week_start,
           category,
           trend_id,
           SUM(normalized_position * chart_weight) / SUM(chart_weight) AS position_score,
           MAX(normalized_position) AS best_chart_score,
           AVG(position) AS avg_raw,
           COUNT(*) AS chart_count,
           MIN(position) AS best_position
    FROM normalized_positions
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
                WHEN a.category = 'games'
                THEN a.best_chart_score
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
    WHERE t.category <> 'games'
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
           END AS interest_score
    FROM wordstat_bounds
),
audience_logs AS (
    SELECT trend_id,
           week_start,
           LN(1 + average_viewers::NUMERIC) AS value
    FROM game_audience_stats
),
audience_bounds AS (
    SELECT a.*,
           MIN(value) OVER (PARTITION BY week_start) AS min_value,
           MAX(value) OVER (PARTITION BY week_start) AS max_value
    FROM audience_logs a
),
audience_scores AS (
    SELECT trend_id,
           week_start,
           CASE WHEN max_value = min_value THEN 1.0
                ELSE (value - min_value) / (max_value - min_value)
           END AS interest_score
    FROM audience_bounds
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
           CASE WHEN s.category = 'games'
                THEN COALESCE(a.interest_score, 0.0)
                ELSE COALESCE(w.interest_score, 0.0)
           END AS wordstat_score,
           s.source_score * CASE WHEN s.category = 'games' THEN 0.65 ELSE 0.85 END +
           CASE WHEN s.category = 'games'
                THEN COALESCE(a.interest_score, 0.0) * 0.35
                ELSE COALESCE(w.interest_score, 0.0) * 0.15
           END AS final_score
    FROM source_scores s
    JOIN collected col USING (week_start, category)
    JOIN category_settings cs ON cs.category = s.category
    LEFT JOIN wordstat_scores w
           ON w.trend_id = s.trend_id AND w.week_start = s.week_start
    LEFT JOIN audience_scores a
           ON a.trend_id = s.trend_id AND a.week_start = s.week_start
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

REFRESH MATERIALIZED VIEW mv_category_rank;
