-- 006: подготовленная неделя не должна становиться видимой до публикации.
-- chart_runs и Wordstat заполняются с воскресенья 22:00, а materialized view
-- обновляется отдельной задачей в понедельник 00:00. Поэтому последнюю видимую
-- неделю определяем по опубликованному рейтингу, а не по сырым запускам чартов.
CREATE OR REPLACE VIEW v_latest_weeks AS
SELECT category, MAX(week_start) AS week_start
FROM mv_category_rank
GROUP BY category;
