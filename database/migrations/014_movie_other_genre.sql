INSERT INTO genres (category, name)
VALUES ('movies', 'Другое')
ON CONFLICT (category, name) DO NOTHING;
