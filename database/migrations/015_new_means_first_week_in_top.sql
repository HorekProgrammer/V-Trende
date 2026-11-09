CREATE OR REPLACE VIEW v_category_top AS
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
       r.weeks_in_top = 1 AS is_new,
       ss.search_count,
       ps.search_count AS prev_search_count,
       t.cover_url
FROM mv_category_rank r
JOIN trends t ON t.id = r.trend_id
LEFT JOIN genres g ON g.id = t.genre_id
LEFT JOIN trend_search_stats ss
       ON ss.trend_id = r.trend_id AND ss.week_start = r.week_start
LEFT JOIN trend_search_stats ps
       ON ps.trend_id = r.trend_id AND ps.week_start = r.week_start - 7;