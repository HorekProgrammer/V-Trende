-- From 2026-11-23, games which are genuinely unavailable in Steam and Epic
-- may enter the ranking from Whatstat alone. Published earlier weeks retain
-- the original 65% store / 35% Whatstat formula and candidate set.
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
    SELECT week_start, category, trend_id,
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
    SELECT trend_id, week_start,
           p_hours_watched * 0.30 + p_average_viewers * 0.20 +
           p_peak_viewers * 0.10 + p_followers_gained * 0.20 +
           p_followers_per_hour * 0.10 + p_hours_streamed * 0.05 +
           p_total_followers * 0.05 AS twitch_score
    FROM twitch_percentiles
),
source_scores AS (
    SELECT a.*,
           CASE WHEN a.category = 'streamers' THEN COALESCE(t.twitch_score, a.position_score)
                WHEN a.category = 'games' THEN a.best_chart_score
                ELSE a.position_score END AS source_score
    FROM chart_aggregates a
    LEFT JOIN twitch_scores t ON t.trend_id = a.trend_id AND t.week_start = a.week_start
),
wordstat_logs AS (
    SELECT t.category, s.trend_id, s.week_start, LN(1 + s.search_count::NUMERIC) AS value
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
    SELECT trend_id, week_start,
           CASE WHEN max_value = min_value THEN 1.0
                ELSE (value - min_value) / (max_value - min_value) END AS interest_score
    FROM wordstat_bounds
),
audience_logs AS (
    SELECT trend_id, week_start, position, average_viewers,
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
    SELECT trend_id, week_start, position, average_viewers,
           (SELECT a2.average_viewers
            FROM game_audience_stats a2
            WHERE a2.week_start = audience_bounds.week_start
            ORDER BY a2.average_viewers DESC, a2.trend_id
            OFFSET 1 LIMIT 1) AS second_viewers,
           CASE WHEN max_value = min_value THEN 1.0
                ELSE (value - min_value) / (max_value - min_value) END AS interest_score
    FROM audience_bounds
),
whatstat_game_candidates AS (
    SELECT a.week_start, 'games'::TEXT AS category, a.trend_id,
           0.0::NUMERIC AS position_score, 0.0::NUMERIC AS best_chart_score,
           NULL::NUMERIC AS avg_raw, 0::BIGINT AS chart_count,
           a.position AS best_position, 0.0::NUMERIC AS source_score
    FROM audience_scores a
    WHERE a.week_start >= DATE '2026-11-23'
      AND NOT EXISTS (
          SELECT 1 FROM chart_aggregates c
          WHERE c.week_start = a.week_start AND c.trend_id = a.trend_id
      )
),
all_source_scores AS (
    SELECT * FROM source_scores
    UNION ALL
    SELECT * FROM whatstat_game_candidates
),
collected AS (
    SELECT r.week_start, c.category, COUNT(*) AS charts_collected
    FROM chart_runs r
    JOIN charts c ON c.id = r.chart_id
    WHERE r.status = 'success'
    GROUP BY r.week_start, c.category
),
scored AS (
    SELECT s.*, col.charts_collected, cs.top_limit,
           CASE WHEN s.category = 'games' THEN COALESCE(a.interest_score, 0.0)
                ELSE COALESCE(w.interest_score, 0.0) END AS wordstat_score,
           CASE
               WHEN s.category = 'games' AND s.week_start >= DATE '2026-11-23'
                    AND s.chart_count = 0
                    AND NOT EXISTS (
                        SELECT 1 FROM trend_source_items i
                        WHERE i.trend_id = s.trend_id AND i.source IN ('steam', 'epic')
                    )
                   THEN COALESCE(a.interest_score, 0.0) * (
                       0.80 + CASE
                           WHEN a.position = 1 AND COALESCE(a.second_viewers, 0) > 0
                           THEN LEAST(
                               0.20,
                               GREATEST(
                                   0.0,
                                   a.average_viewers::NUMERIC / a.second_viewers - 1.0
                               ) * 0.20
                           )
                           ELSE 0.0
                       END
                   )
               ELSE s.source_score * CASE WHEN s.category = 'games' THEN 0.65 ELSE 0.97 END +
                    CASE WHEN s.category = 'games' THEN COALESCE(a.interest_score, 0.0) * 0.35
                         ELSE COALESCE(w.interest_score, 0.0) * 0.03 END
           END AS final_score
    FROM all_source_scores s
    JOIN collected col USING (week_start, category)
    JOIN category_settings cs ON cs.category = s.category
    LEFT JOIN wordstat_scores w ON w.trend_id = s.trend_id AND w.week_start = s.week_start
    LEFT JOIN audience_scores a ON a.trend_id = s.trend_id AND a.week_start = s.week_start
    WHERE s.chart_count >= LEAST(cs.min_charts, col.charts_collected)
       OR (s.category = 'games' AND s.week_start >= DATE '2026-11-23'
           AND s.chart_count = 0 AND a.trend_id IS NOT NULL)
),
ranked AS (
    SELECT s.*,
           ROW_NUMBER() OVER (
               PARTITION BY week_start, category
               ORDER BY final_score DESC, chart_count DESC, best_position, trend_id
           ) AS rank
    FROM scored s
)
SELECT week_start, category, trend_id, rank::INTEGER AS rank,
       ROUND((final_score * 100)::NUMERIC, 2) AS score,
       ROUND((source_score * 100)::NUMERIC, 2) AS source_score,
       ROUND((wordstat_score * 100)::NUMERIC, 2) AS wordstat_score,
       ROUND(avg_raw, 2) AS avg_position,
       chart_count::INTEGER AS chart_count,
       charts_collected::INTEGER AS charts_collected,
       best_position::INTEGER AS best_position
FROM ranked
WHERE rank <= top_limit;

DROP VIEW v_trend_history;
DROP VIEW v_main_feed;
DROP VIEW v_category_top_latest;
DROP VIEW v_category_top;
DROP VIEW v_latest_weeks;
DROP MATERIALIZED VIEW mv_category_rank;

CREATE MATERIALIZED VIEW mv_category_rank AS
WITH first_seen AS (
    SELECT trend_id, MIN(week_start) AS first_seen_week
    FROM (
        SELECT trend_id, week_start FROM v_chart_entries
        UNION ALL
        SELECT trend_id, week_start FROM game_audience_stats
        WHERE week_start >= DATE '2026-11-23'
    ) observations
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
SELECT h.week_start, h.category, h.trend_id, h.rank, h.score,
       h.source_score, h.wordstat_score, h.avg_position, h.chart_count,
       h.charts_collected, h.best_position,
       CASE WHEN h.prev_week = h.week_start - 7 THEN h.prev_rank_any END AS prev_rank,
       h.peak_rank, h.weeks_in_top::INTEGER AS weeks_in_top, fs.first_seen_week
FROM history h
JOIN first_seen fs ON fs.trend_id = h.trend_id;

CREATE UNIQUE INDEX uq_mv_category_rank ON mv_category_rank (week_start, category, trend_id);
CREATE INDEX ix_mv_category_rank_top ON mv_category_rank (category, week_start, rank);
CREATE INDEX ix_mv_category_rank_trend ON mv_category_rank (trend_id, week_start);

CREATE VIEW v_latest_weeks AS
SELECT category, MAX(week_start) AS week_start
FROM mv_category_rank
GROUP BY category;

CREATE VIEW v_category_top AS
SELECT r.week_start, r.category, r.rank, r.score, r.source_score, r.wordstat_score,
       r.trend_id, t.title, t.subtitle, g.name AS genre, r.avg_position,
       r.chart_count, r.charts_collected, r.best_position, r.prev_rank,
       r.prev_rank - r.rank AS rank_change, r.peak_rank, r.weeks_in_top,
       r.first_seen_week, r.weeks_in_top = 1 AS is_new,
       ss.search_count, ps.search_count AS prev_search_count, t.cover_url
FROM mv_category_rank r
JOIN trends t ON t.id = r.trend_id
LEFT JOIN genres g ON g.id = t.genre_id
LEFT JOIN trend_search_stats ss ON ss.trend_id = r.trend_id AND ss.week_start = r.week_start
LEFT JOIN trend_search_stats ps ON ps.trend_id = r.trend_id AND ps.week_start = r.week_start - 7;

CREATE VIEW v_category_top_latest AS
SELECT t.* FROM v_category_top t
JOIN v_latest_weeks l ON l.category = t.category AND l.week_start = t.week_start;

CREATE VIEW v_main_feed AS
SELECT ROW_NUMBER() OVER (
           ORDER BY l.score DESC, l.search_count DESC NULLS LAST,
                    l.rank, l.category, l.trend_id
       )::INTEGER AS feed_rank,
       l.*
FROM v_category_top_latest l;

CREATE VIEW v_trend_history AS
WITH weeks AS (
    SELECT trend_id, week_start FROM v_chart_entries
    UNION
    SELECT trend_id, week_start FROM trend_search_stats
    UNION
    SELECT trend_id, week_start FROM game_audience_stats
    WHERE week_start >= DATE '2026-11-23'
)
SELECT wk.trend_id, wk.week_start, w.rank AS category_rank, w.score,
       w.source_score, w.wordstat_score, w.avg_position, w.chart_count,
       ss.search_count
FROM weeks wk
LEFT JOIN mv_category_rank w ON w.trend_id = wk.trend_id AND w.week_start = wk.week_start
LEFT JOIN trend_search_stats ss ON ss.trend_id = wk.trend_id AND ss.week_start = wk.week_start;
