-- 016: up to three ordered genres per trend while keeping trends.genre_id as the primary genre.

ALTER TABLE trends
    ADD COLUMN genres_resolved_at TIMESTAMPTZ;

ALTER TABLE trends
    ADD CONSTRAINT uq_trends_id_category UNIQUE (id, category);

CREATE TABLE trend_genres (
    trend_id BIGINT NOT NULL,
    genre_id SMALLINT NOT NULL,
    category TEXT NOT NULL,
    position SMALLINT NOT NULL CHECK (position BETWEEN 1 AND 3),
    PRIMARY KEY (trend_id, genre_id),
    CONSTRAINT uq_trend_genres_position UNIQUE (trend_id, position),
    CONSTRAINT fk_trend_genres_trend
        FOREIGN KEY (trend_id, category) REFERENCES trends (id, category) ON DELETE CASCADE,
    CONSTRAINT fk_trend_genres_genre
        FOREIGN KEY (genre_id, category) REFERENCES genres (id, category)
);

CREATE INDEX ix_trend_genres_genre ON trend_genres (category, genre_id, trend_id);

INSERT INTO trend_genres (trend_id, genre_id, category, position)
SELECT id, genre_id, category, 1
FROM trends
WHERE genre_id IS NOT NULL;

CREATE FUNCTION sync_primary_trend_genre() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.genre_id IS NULL THEN
        DELETE FROM trend_genres WHERE trend_id = NEW.id AND position = 1;
        RETURN NEW;
    END IF;
    DELETE FROM trend_genres
    WHERE trend_id = NEW.id AND (position = 1 OR genre_id = NEW.genre_id);
    INSERT INTO trend_genres (trend_id, genre_id, category, position)
    VALUES (NEW.id, NEW.genre_id, NEW.category, 1);
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_sync_primary_trend_genre
AFTER INSERT OR UPDATE OF genre_id, category ON trends
FOR EACH ROW EXECUTE FUNCTION sync_primary_trend_genre();

CREATE FUNCTION trend_genre_names(p_trend_id BIGINT) RETURNS TEXT[]
LANGUAGE sql STABLE AS $$
    SELECT COALESCE(array_agg(g.name ORDER BY tg.position), ARRAY[]::TEXT[])
    FROM trend_genres tg
    JOIN genres g ON g.id = tg.genre_id
    WHERE tg.trend_id = p_trend_id
$$;
