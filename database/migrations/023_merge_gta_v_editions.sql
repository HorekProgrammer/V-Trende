-- Legacy and Enhanced are editions of the same game. Keep Enhanced as the
-- canonical object, attach both storefront IDs to it and collapse duplicate
-- chart rows to the better position.
DO $$
DECLARE
    winner_id BIGINT;
BEGIN
    CREATE TEMP TABLE gta_v_merge_ids ON COMMIT DROP AS
    SELECT id
    FROM trends
    WHERE category = 'games'
      AND match_key IN (
          'grand theft auto v',
          'grand theft auto v legacy',
          'grand theft auto v enhanced'
      );

    SELECT t.id INTO winner_id
    FROM trends t
    JOIN gta_v_merge_ids m ON m.id = t.id
    ORDER BY CASE t.match_key
                 WHEN 'grand theft auto v enhanced' THEN 0
                 WHEN 'grand theft auto v' THEN 1
                 ELSE 2
             END,
             t.id
    LIMIT 1;

    IF winner_id IS NULL THEN
        RETURN;
    END IF;

    CREATE TEMP TABLE gta_v_history ON COMMIT DROP AS
    SELECT run_id, MIN(position)::SMALLINT AS position
    FROM trend_history
    WHERE trend_id IN (SELECT id FROM gta_v_merge_ids)
    GROUP BY run_id;

    DELETE FROM trend_history
    WHERE trend_id IN (SELECT id FROM gta_v_merge_ids);

    INSERT INTO trend_history (run_id, trend_id, position)
    SELECT run_id, winner_id, position
    FROM gta_v_history;

    CREATE TEMP TABLE gta_v_audience ON COMMIT DROP AS
    SELECT DISTINCT ON (week_start)
           week_start, source_title, source_category_id, source_url,
           position, average_viewers, collected_at
    FROM game_audience_stats
    WHERE trend_id IN (SELECT id FROM gta_v_merge_ids)
    ORDER BY week_start, average_viewers DESC, position, collected_at DESC;

    DELETE FROM game_audience_stats
    WHERE trend_id IN (SELECT id FROM gta_v_merge_ids);

    INSERT INTO game_audience_stats (
        trend_id, week_start, source_title, source_category_id,
        source_url, position, average_viewers, collected_at
    )
    SELECT winner_id, week_start, 'Grand Theft Auto V', source_category_id,
           source_url, position, average_viewers, collected_at
    FROM gta_v_audience;

    CREATE TEMP TABLE gta_v_search ON COMMIT DROP AS
    SELECT DISTINCT ON (week_start)
           week_start, query, search_count, collected_at
    FROM trend_search_stats
    WHERE trend_id IN (SELECT id FROM gta_v_merge_ids)
    ORDER BY week_start, search_count DESC, collected_at DESC;

    DELETE FROM trend_search_stats
    WHERE trend_id IN (SELECT id FROM gta_v_merge_ids);

    INSERT INTO trend_search_stats (trend_id, week_start, query, search_count, collected_at)
    SELECT winner_id, week_start, query, search_count, collected_at
    FROM gta_v_search;

    UPDATE trend_source_items
    SET trend_id = winner_id
    WHERE trend_id IN (SELECT id FROM gta_v_merge_ids)
      AND trend_id <> winner_id;

    DELETE FROM trends
    WHERE id IN (SELECT id FROM gta_v_merge_ids)
      AND id <> winner_id;

    UPDATE trends
    SET title = 'Grand Theft Auto V',
        match_key = 'grand theft auto v'
    WHERE id = winner_id;
END
$$;

REFRESH MATERIALIZED VIEW mv_category_rank;
