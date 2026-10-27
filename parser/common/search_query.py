"""Поисковая фраза для Wordstat по умолчанию.

Если у тренда задано trends.search_query, используется оно; иначе фраза
строится здесь. Фраза нормализуется (normalize_text): так в неё не попадают
символы-операторы Wordstat (!, +, -, кавычки, скобки) и пометки feat./Explicit.
"""

from .normalize import main_artist, normalize_text

MAX_QUERY_LENGTH = 400


def default_search_query(category: str, title: str, subtitle: str | None = None) -> str:
    if category == "music" and subtitle:
        # Название песни без исполнителя слишком неоднозначно.
        phrase = f"{main_artist([subtitle])} {title}"
    elif category == "movies":
        # «Мастер и Маргарита» — ещё и книга; уточняем, что ищем фильм.
        phrase = f"{title} фильм"
    else:
        phrase = title
    query = normalize_text(phrase)
    if not query:
        raise ValueError(f"Не удалось составить поисковую фразу для {title!r}.")
    return query[:MAX_QUERY_LENGTH].strip()
