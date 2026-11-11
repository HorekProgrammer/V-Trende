-- Covers are stored by the application and served from its own /media path.
ALTER TABLE trends DROP CONSTRAINT IF EXISTS trends_cover_url_check;
ALTER TABLE trends
    ADD CONSTRAINT trends_cover_url_check CHECK (
        cover_url IS NULL OR (
            length(cover_url) <= 2000
            AND (cover_url LIKE 'https://%' OR cover_url LIKE '/media/covers/%')
        )
    );
