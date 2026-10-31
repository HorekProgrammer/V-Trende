-- 008: обложки трендов.
--
-- cover_url    — https-ссылка на картинку (постер фильма, обложка игры и т. п.);
--                пусто, если ни один источник её не дал — тогда сайт рисует заглушку.
-- cover_source — источник, из которого взята обложка. Тот же источник может
--                обновить ссылку, другой — нет: иначе у игры из Steam и Epic
--                картинка менялась бы при каждой загрузке.
ALTER TABLE trends
    ADD COLUMN cover_url    TEXT CHECK (cover_url LIKE 'https://%' AND length(cover_url) <= 2000),
    ADD COLUMN cover_source TEXT;

-- Представления карточек: определения из 005 без изменений + cover_url в конце.
-- Новый столбец добавляется последним, поэтому CREATE OR REPLACE допустим
-- и зависящие представления не нужно пересоздавать.
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
       r.first_seen_week = r.week_start AS is_new,
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

CREATE OR REPLACE VIEW v_category_top_latest AS
SELECT t.*
FROM v_category_top t
JOIN v_latest_weeks l ON l.category = t.category AND l.week_start = t.week_start;

CREATE OR REPLACE VIEW v_main_feed AS
SELECT ROW_NUMBER() OVER (
           ORDER BY l.score DESC, l.search_count DESC NULLS LAST, l.rank, l.category, l.trend_id
       )::INTEGER AS feed_rank,
       l.*
FROM v_category_top_latest l;
