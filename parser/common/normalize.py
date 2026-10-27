"""Нормализация названий для сопоставления одного объекта между источниками."""

import re
import unicodedata

# Пометки о приглашённых исполнителях: всё после них отбрасывается.
_FEAT_RE = re.compile(r"\s(?:feat\.?|ft\.?|featuring)\s.*$")
# Служебные пометки в скобках: (feat. ...), [Explicit], (prod. ...).
# Остальные скобки, например (Remix) или (Live), сохраняются: это другой трек.
_BRACKETS_RE = re.compile(
    r"[(\[]\s*(?:feat\.?|ft\.?|featuring|prod\.?|explicit|clean)\b[^)\]]*[)\]]"
)
# Разделители нескольких исполнителей в одной строке.
_ARTIST_SEPARATORS_RE = re.compile(r"\s*(?:,|&|\sx\s|\sи\s|\sfeat\.?\s|\sft\.?\s)\s*")
_NOT_WORD_RE = re.compile(r"[^\w\s]")
_SPACES_RE = re.compile(r"\s+")


def normalize_text(value: str) -> str:
    """Регистр, ё/е, пометки feat./prod./explicit, пунктуация и лишние пробелы не влияют на результат."""
    # ™ ® © убираются до NFKC, иначе ™ превращается в буквы «TM».
    text = re.sub(r"[™®©℠]", " ", value)
    text = unicodedata.normalize("NFKC", text).casefold().replace("ё", "е")
    text = _BRACKETS_RE.sub(" ", text)
    text = _FEAT_RE.sub("", f" {text} ").strip()
    text = _NOT_WORD_RE.sub(" ", text).replace("_", " ")
    return _SPACES_RE.sub(" ", text).strip()


def main_artist(artists: list[str]) -> str:
    """Первый исполнитель. Сервисы по-разному записывают совместные треки
    («A & B» одной строкой или списком ["A", "B"]), но первый обычно совпадает."""
    if not artists:
        return ""
    return _ARTIST_SEPARATORS_RE.split(artists[0].strip(), maxsplit=1)[0]


def match_key(title: str, artists: list[str] | None = None) -> str:
    """Ключ сопоставления: «исполнитель|название» для музыки, «название» для остального."""
    normalized_title = normalize_text(title)
    if not normalized_title:
        raise ValueError(f"Пустое название после нормализации: {title!r}")
    if artists is None:
        return normalized_title
    artist = normalize_text(main_artist(artists))
    if not artist:
        raise ValueError(f"Не указан исполнитель для трека {title!r}")
    return f"{artist}|{normalized_title}"
