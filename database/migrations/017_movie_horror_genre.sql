INSERT INTO genres (category, name)
VALUES ('movies', 'Ужасы')
ON CONFLICT (category, name) DO NOTHING;

-- Existing movie classifications predate the separate horror genre.
UPDATE trends SET genres_resolved_at = NULL WHERE category = 'movies';
