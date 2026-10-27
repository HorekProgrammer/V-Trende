-- 002: справочник жанров.
-- Жанр у тренда один и выбирается из фиксированного списка своей категории
-- (те же значения, что в фильтре фронтенда). Источник жанров пока не подключён:
-- в дальнейшем их будет проставлять нейросеть, до этого genre_id остаётся пустым.

CREATE TABLE genres (
    id       SMALLINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    category TEXT NOT NULL
             CHECK (category IN ('games', 'music', 'movies', 'streamers')),
    name     TEXT NOT NULL,
    CONSTRAINT uq_genres_category_name UNIQUE (category, name),
    -- Нужен для составного внешнего ключа из trends: жанр той же категории.
    CONSTRAINT uq_genres_id_category UNIQUE (id, category)
);

INSERT INTO genres (category, name) VALUES
    ('music', 'Поп'),
    ('music', 'Рэп / Хип-хоп'),
    ('music', 'Рок'),
    ('music', 'Электроника'),
    ('music', 'Инди'),
    ('movies', 'Драма'),
    ('movies', 'Боевик'),
    ('movies', 'Триллер'),
    ('movies', 'Комедия'),
    ('movies', 'Фантастика'),
    ('games', 'Экшен'),
    ('games', 'RPG'),
    ('games', 'Стратегии'),
    ('games', 'Шутеры'),
    ('games', 'Инди'),
    ('streamers', 'Игры'),
    ('streamers', 'Just Chatting'),
    ('streamers', 'Музыка'),
    ('streamers', 'IRL'),
    ('streamers', 'Творчество');

-- Свободный текст заменяется ссылкой на справочник.
ALTER TABLE trends DROP COLUMN genre;
ALTER TABLE trends ADD COLUMN genre_id SMALLINT;
-- Составной ключ не даёт назначить игре музыкальный жанр.
-- Пока genre_id пуст (NULL), ограничение не проверяется.
ALTER TABLE trends
    ADD CONSTRAINT fk_trends_genre
    FOREIGN KEY (genre_id, category) REFERENCES genres (id, category);

CREATE INDEX ix_trends_category_genre ON trends (category, genre_id);
