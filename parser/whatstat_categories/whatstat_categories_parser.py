"""Russian-language Twitch game categories from Whatstat."""

from html.parser import HTMLParser
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


BASE_URL = "https://whatstat.ru/twitch/categories"
DEFAULT_PAGES = 10
_CATEGORY_PATH_RE = re.compile(r"^/twitch/categories/([^/?#]+)$")
_NUMBER_RE = re.compile(r"^(\d+(?:[.,]\d+)?)\s*(тыс\.|млн)?$", re.IGNORECASE)


def parse_viewers(value: str) -> int:
    text = "".join(value.replace("\xa0", " ").split())
    match = _NUMBER_RE.fullmatch(text)
    if match is None:
        raise ValueError(f"Некорректное число зрителей Whatstat: {value!r}")
    number = float(match.group(1).replace(",", "."))
    multiplier = {None: 1, "тыс.": 1_000, "млн": 1_000_000}[match.group(2).lower() if match.group(2) else None]
    return round(number * multiplier)


class _CategoryTableParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_body = False
        self.in_row = False
        self.in_cell = False
        self.cell_parts = []
        self.cells = []
        self.category_id = None
        self.rows = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "tbody":
            self.in_body = True
        elif self.in_body and tag == "tr":
            self.in_row = True
            self.cells = []
            self.category_id = None
        elif self.in_row and tag == "td":
            self.in_cell = True
            self.cell_parts = []
        elif self.in_cell and tag == "a":
            match = _CATEGORY_PATH_RE.match(attributes.get("href", ""))
            if match:
                self.category_id = match.group(1)

    def handle_data(self, data):
        if self.in_cell:
            self.cell_parts.append(data)

    def handle_endtag(self, tag):
        if tag == "td" and self.in_cell:
            self.cells.append(" ".join("".join(self.cell_parts).split()))
            self.in_cell = False
        elif tag == "tr" and self.in_row:
            if len(self.cells) >= 3 and self.category_id:
                try:
                    position = int(self.cells[0])
                    viewers = parse_viewers(self.cells[2])
                except ValueError:
                    pass
                else:
                    self.rows.append({
                        "position": position,
                        "title": self.cells[1],
                        "average_viewers": viewers,
                        "category_id": self.category_id,
                        "url": f"https://whatstat.ru/twitch/categories/{self.category_id}",
                    })
            self.in_row = False
        elif tag == "tbody":
            self.in_body = False


def parse_categories(html: str) -> list[dict]:
    parser = _CategoryTableParser()
    parser.feed(html)
    parser.close()
    if not parser.rows:
        raise RuntimeError("Whatstat не вернул таблицу категорий")
    return parser.rows


def _fetch_page(page: int, timeout: float) -> str:
    url = BASE_URL if page == 1 else f"{BASE_URL}?page={page}"
    request = Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; V-Trende/1.0)",
        "Accept-Language": "ru-RU,ru;q=0.9",
    })
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8")
    except (HTTPError, URLError, TimeoutError, OSError) as error:
        raise RuntimeError(f"Whatstat: страница {page} недоступна") from error


def get_whatstat_categories(*, pages: int = DEFAULT_PAGES, timeout: float = 30) -> list[dict]:
    if type(pages) is not int or pages <= 0:
        raise ValueError("pages должно быть положительным целым числом")
    result = []
    seen_ids = set()
    for page in range(1, pages + 1):
        rows = parse_categories(_fetch_page(page, timeout))
        for row in rows:
            if row["category_id"] not in seen_ids:
                seen_ids.add(row["category_id"])
                result.append(row)
    if not result:
        raise RuntimeError("Whatstat не вернул ни одной категории")
    result.sort(key=lambda row: row["position"])
    return result
