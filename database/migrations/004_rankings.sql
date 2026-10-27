-- 004: правила рейтинга категорий и представления для выдачи данных.
--
-- Все представления считают только успешные запуски сбора (chart_runs.status = 'success').
-- Позиции «до сравнения» не преобразуются: общий топ категории — средняя позиция
-- объекта по чартам категории, в которых он есть.
--
-- Типовое использование (бэкенд подставляет параметры):
--   топ категории сейчас:   SELECT * FROM v_category_top_latest WHERE category = 'music' ORDER BY rank;
--   «По новизне»:           ... ORDER BY first_seen_week DESC, rank;
--   «Растущие»:             ... WHERE rank_change > 0 ORDER BY rank_change DESC, rank;
--   главная лента:          SELECT * FROM v_main_feed ORDER BY feed_rank LIMIT 20 OFFSET 0;
--   топ чарта:              SELECT * FROM v_chart_top WHERE chart_id = 1 AND week_start = '2026-10-19' ORDER BY position;
--   график тренда:          SELECT * FROM v_trend_history WHERE trend_id = 42 ORDER BY week_start;
--
-- Тяжёлая часть (средние позиции, места, динамика по всей истории) хранится
-- в материализованном представлении mv_category_rank: данные меняются раз в неделю,
-- а на пятилетней истории расчёт «на лету» занимает сотни миллисекунд.
-- Его нужно обновлять после загрузки чартов: database.load_outbox и database.seed
-- делают это сами; вручную — REFRESH MATERIALIZED VIEW CONCURRENTLY mv_category_rank;

-- Настройки рейтинга по категориям.
--   top_limit  — сколько объектов показывается в топе категории (300 в неделю всего);
--   min_charts — в скольких чартах категории объект должен присутствовать,
--                чтобы попасть в общий топ (защита от случайного единичного попадания).
-- Если за неделю успешно собрано меньше чартов, чем min_charts, порог снижается
-- до числа собранных, иначе сбой одного парсера опустошил бы топ.
CREATE TABLE category_settings (
    category   TEXT PRIMARY KEY
               CHECK (category IN ('games', 'music', 'movies', 'streamers')),
    top_limit  SMALLINT NOT NULL CHECK (top_limit > 0),
    min_charts SMALLINT NOT NULL CHECK (min_charts > 0)
);

INSERT INTO category_settings (category, top_limit, min_charts) VALUES
    ('music', 100, 2),     -- 6 чартов
    ('games', 100, 2),     -- 4 чарта: Steam ×2, Epic ×2
    ('movies', 50, 1),     -- 2 чарта: популярное и кассовые сборы
    ('streamers', 50, 1);  -- 1 чарт: Twitch

-- Позиции успешных запусков: одна строка — объект в чарте за неделю.
CREATE VIEW v_chart_entries AS
SELECT r.week_start,
       c.category,
       c.id     AS chart_id,
       c.source,
       c.name   AS chart_name,
       h.trend_id,
       h.position
FROM trend_history h
JOIN chart_runs r ON r.id = h.run_id AND r.status = 'success'
JOIN charts c ON c.id = r.chart_id;

-- Топ конкретного чарта с позицией на прошлой неделе.
-- Прошлая позиция берётся оконной функцией LAG: самосоединение представления
-- заставило бы PostgreSQL пересчитывать его для каждой строки.
CREATE VIEW v_chart_top AS
WITH entries AS (
    SELECT e.*,
           LAG(e.week_start) OVER previous AS prev_week,
           LAG(e.position)   OVER previous AS prev_position_any
    FROM v_chart_entries e
    WINDOW previous AS (PARTITION BY e.chart_id, e.trend_id ORDER BY e.week_start)
)
SELECT e.week_start,
       e.category,
       e.chart_id,
       e.source,
       e.chart_name,
       e.position,
       CASE WHEN e.prev_week = e.week_start - 7 THEN e.prev_position_any END AS prev_position,
       e.trend_id,
       t.title,
       t.subtitle,
       g.name AS genre
FROM entries e
JOIN trends t ON t.id = e.trend_id
LEFT JOIN genres g ON g.id = t.genre_id;

-- Общий рейтинг категории за каждую неделю: средняя позиция по чартам категории.
-- Порядок: средняя позиция ↑, число чартов ↓, лучшая позиция ↑.
CREATE VIEW v_category_weekly_rank AS
WITH stats AS (
    SELECT week_start,
           category,
           trend_id,
           AVG(position)  AS avg_raw,
           COUNT(*)       AS chart_count,
           MIN(position)  AS best_position
    FROM v_chart_entries
    GROUP BY week_start, category, trend_id
),
collected AS (
    SELECT r.week_start, c.category, COUNT(*) AS charts_collected
    FROM chart_runs r
    JOIN charts c ON c.id = r.chart_id
    WHERE r.status = 'success'
    GROUP BY r.week_start, c.category
),
ranked AS (
    SELECT s.*,
           col.charts_collected,
           cs.top_limit,
           ROW_NUMBER() OVER (
               PARTITION BY s.week_start, s.category
               ORDER BY s.avg_raw, s.chart_count DESC, s.best_position, s.trend_id
           ) AS rank
    FROM stats s
    JOIN collected col USING (week_start, category)
    JOIN category_settings cs ON cs.category = s.category
    WHERE s.chart_count >= LEAST(cs.min_charts, col.charts_collected)
)
SELECT week_start,
       category,
       trend_id,
       rank::INTEGER                AS rank,
       ROUND(avg_raw, 2)            AS avg_position,
       chart_count::INTEGER         AS chart_count,
       charts_collected::INTEGER    AS charts_collected,
       best_position::INTEGER       AS best_position
FROM ranked
WHERE rank <= top_limit;

-- Места в топе категории по всей истории вместе с динамикой (материализовано):
--   prev_rank      — место в топе на прошлой неделе (NULL — не было в топе);
--   peak_rank      — лучшее место за всю историю до этой недели включительно;
--   weeks_in_top   — сколько недель объект был в топе до этой недели включительно;
--   first_seen_week — первое появление объекта в любом чарте.
-- Места на прошлой неделе считаются оконной функцией LAG: самосоединение
-- представления заставило бы PostgreSQL пересчитывать его для каждой строки.
CREATE MATERIALIZED VIEW mv_category_rank AS
WITH first_seen AS (
    SELECT trend_id, MIN(week_start) AS first_seen_week
    FROM v_chart_entries
    GROUP BY trend_id
),
history AS (
    SELECT w.*,
           LAG(w.week_start) OVER previous   AS prev_week,
           LAG(w.rank)       OVER previous   AS prev_rank_any,
           MIN(w.rank)       OVER cumulative AS peak_rank,
           COUNT(*)          OVER cumulative AS weeks_in_top
    FROM v_category_weekly_rank w
    WINDOW previous   AS (PARTITION BY w.category, w.trend_id ORDER BY w.week_start),
           cumulative AS (PARTITION BY w.category, w.trend_id ORDER BY w.week_start
                          ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
)
SELECT h.week_start,
       h.category,
       h.trend_id,
       h.rank,
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

-- Уникальный индекс обязателен для REFRESH ... CONCURRENTLY (обновление без блокировки чтения).
CREATE UNIQUE INDEX uq_mv_category_rank ON mv_category_rank (week_start, category, trend_id);
CREATE INDEX ix_mv_category_rank_top ON mv_category_rank (category, week_start, rank);
CREATE INDEX ix_mv_category_rank_trend ON mv_category_rank (trend_id, week_start);

-- Топ категории со всеми полями карточки:
--   rank_change    — prev_rank − rank, > 0 означает рост;
--   is_new         — неделя первого появления объекта в чартах;
--   search_count, prev_search_count — частота запросов Wordstat за эту и прошлую неделю
--                    (берутся из таблицы напрямую, обновлять представление не нужно).
CREATE VIEW v_category_top AS
SELECT r.week_start,
       r.category,
       r.rank,
       r.trend_id,
       t.title,
       t.subtitle,
       g.name                                AS genre,
       r.avg_position,
       r.chart_count,
       r.charts_collected,
       r.best_position,
       r.prev_rank,
       r.prev_rank - r.rank                  AS rank_change,
       r.peak_rank,
       r.weeks_in_top,
       r.first_seen_week,
       r.first_seen_week = r.week_start      AS is_new,
       ss.search_count,
       ps.search_count                       AS prev_search_count
FROM mv_category_rank r
JOIN trends t ON t.id = r.trend_id
LEFT JOIN genres g ON g.id = t.genre_id
LEFT JOIN trend_search_stats ss
       ON ss.trend_id = r.trend_id AND ss.week_start = r.week_start
LEFT JOIN trend_search_stats ps
       ON ps.trend_id = r.trend_id AND ps.week_start = r.week_start - 7;

-- Последняя неделя, за которую по категории есть хотя бы один успешный сбор.
CREATE VIEW v_latest_weeks AS
SELECT c.category, MAX(r.week_start) AS week_start
FROM chart_runs r
JOIN charts c ON c.id = r.chart_id
WHERE r.status = 'success'
GROUP BY c.category;

-- Актуальный топ каждой категории.
CREATE VIEW v_category_top_latest AS
SELECT t.*
FROM v_category_top t
JOIN v_latest_weeks l ON l.category = t.category AND l.week_start = t.week_start;

-- Смешанная лента главной страницы: актуальные топы всех категорий,
-- упорядоченные по частоте запросов Wordstat (общая шкала для разных категорий).
-- Объекты без данных Wordstat идут в конце по месту в своей категории.
CREATE VIEW v_main_feed AS
SELECT ROW_NUMBER() OVER (
           ORDER BY l.search_count DESC NULLS LAST, l.rank, l.category, l.trend_id
       )::INTEGER AS feed_rank,
       l.*
FROM v_category_top_latest l;

-- История тренда по неделям для графика: место в топе категории,
-- средняя позиция и частота запросов. Позиции по отдельным чартам — в v_chart_top.
CREATE VIEW v_trend_history AS
WITH weeks AS (
    SELECT trend_id, week_start FROM v_chart_entries
    UNION
    SELECT trend_id, week_start FROM trend_search_stats
)
SELECT wk.trend_id,
       wk.week_start,
       w.rank         AS category_rank,
       w.avg_position,
       w.chart_count,
       ss.search_count
FROM weeks wk
LEFT JOIN mv_category_rank w
       ON w.trend_id = wk.trend_id AND w.week_start = wk.week_start
LEFT JOIN trend_search_stats ss
       ON ss.trend_id = wk.trend_id AND ss.week_start = wk.week_start;
