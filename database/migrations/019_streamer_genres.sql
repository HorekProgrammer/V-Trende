-- Streamer filters are intentionally limited to games and Just Chatting.
DELETE FROM trend_genres tg
USING genres g
WHERE tg.genre_id = g.id
  AND g.category = 'streamers'
  AND g.name NOT IN ('Игры', 'Just Chatting');

UPDATE trends t
SET genre_id = NULL,
    genres_resolved_at = NULL
FROM genres g
WHERE t.genre_id = g.id
  AND t.category = 'streamers'
  AND g.name NOT IN ('Игры', 'Just Chatting');

DELETE FROM genres
WHERE category = 'streamers'
  AND name NOT IN ('Игры', 'Just Chatting');
