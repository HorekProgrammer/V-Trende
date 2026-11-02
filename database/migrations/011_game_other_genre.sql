INSERT INTO genres (category, name)
VALUES ('games', 'Другое')
ON CONFLICT (category, name) DO NOTHING;
