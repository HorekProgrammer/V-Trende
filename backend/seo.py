"""Search-engine discovery documents for the public website."""

from __future__ import annotations

import html
import json
import os
from pathlib import Path
from xml.etree import ElementTree


SITE_URL = "https://vcharte.com"
PUBLIC_PATHS = (
    "/",
    "/category/music",
    "/category/movies",
    "/category/games",
    "/category/streamers",
)
SITEMAP_NAMESPACE = "http://www.sitemaps.org/schemas/sitemap/0.9"
CATEGORY_META = {
    "music": (
        "Популярная музыка — рейтинг недели | В ЧАРТЕ",
        "Актуальный рейтинг популярной музыки: позиции треков, изменения за неделю, исторические максимумы и динамика популярности.",
    ),
    "movies": (
        "Популярные фильмы — рейтинг недели | В ЧАРТЕ",
        "Актуальный рейтинг популярных фильмов: позиции, изменения за неделю, исторические максимумы и динамика популярности.",
    ),
    "games": (
        "Популярные игры — рейтинг недели | В ЧАРТЕ",
        "Актуальный рейтинг популярных игр: позиции, изменения за неделю, исторические максимумы и динамика популярности.",
    ),
    "streamers": (
        "Популярные стримеры — рейтинг недели | В ЧАРТЕ",
        "Актуальный рейтинг популярных стримеров: позиции, изменения за неделю, исторические максимумы и динамика популярности.",
    ),
}
PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIST_DIR = Path(
    os.getenv("FRONTEND_DIST_DIR", str(PROJECT_ROOT / "frontend" / "dist"))
)


def sitemap_xml(trend_ids: list[int]) -> bytes:
    """Build a sitemap from stable routes and published trend identifiers."""
    ElementTree.register_namespace("", SITEMAP_NAMESPACE)
    root = ElementTree.Element(f"{{{SITEMAP_NAMESPACE}}}urlset")
    paths = [*PUBLIC_PATHS, *(f"/trend/{trend_id}" for trend_id in trend_ids)]
    for path in paths:
        url = ElementTree.SubElement(root, f"{{{SITEMAP_NAMESPACE}}}url")
        location = ElementTree.SubElement(url, f"{{{SITEMAP_NAMESPACE}}}loc")
        location.text = f"{SITE_URL}{path}"
    return ElementTree.tostring(root, encoding="utf-8", xml_declaration=True)


def load_frontend_index() -> str:
    """Load the exact Vite shell whose assets are served by Nginx."""
    return (FRONTEND_DIST_DIR / "index.html").read_text(encoding="utf-8")


def _initial_data_script(data: dict) -> str:
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    payload = (
        payload.replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )
    return f"<script>window.__VCHARTE_INITIAL_DATA__={payload}</script>"


def _absolute_url(value: str | None) -> str | None:
    if not value:
        return None
    if value.startswith("https://"):
        return value
    if value.startswith("/"):
        return f"{SITE_URL}{value}"
    return None


def _metadata(
    index_html: str,
    *,
    title: str,
    description: str,
    canonical: str,
    image: str | None = None,
) -> str:
    escaped_title = html.escape(title, quote=True)
    escaped_description = html.escape(description, quote=True)
    escaped_canonical = html.escape(canonical, quote=True)
    index_html = index_html.replace(
        index_html[index_html.index("<title>"):index_html.index("</title>") + 8],
        f"<title>{escaped_title}</title>",
        1,
    )
    tags = [
        f'<meta name="description" content="{escaped_description}">',
        f'<link rel="canonical" href="{escaped_canonical}">',
        f'<meta property="og:title" content="{escaped_title}">',
        f'<meta property="og:description" content="{escaped_description}">',
        f'<meta property="og:url" content="{escaped_canonical}">',
        '<meta property="og:type" content="website">',
        '<meta property="og:site_name" content="В ЧАРТЕ">',
        '<meta property="og:locale" content="ru_RU">',
    ]
    absolute_image = _absolute_url(image)
    if absolute_image:
        tags.append(
            f'<meta property="og:image" content="{html.escape(absolute_image, quote=True)}">'
        )
    return index_html.replace("</head>", f"  {' '.join(tags)}\n  </head>", 1)


def _ranking(items: list[dict], heading: str) -> str:
    rows = []
    for item in items:
        trend_id = int(item["key"])
        rank = html.escape(str(item.get("rank", "")))
        title = html.escape(str(item.get("title", "")))
        subtitle = html.escape(str(item.get("subtitle", "")))
        rows.append(
            '<li class="seo-ranking-card">'
            f'<a class="seo-ranking-link" href="/trend/{trend_id}">'
            f'<span aria-label="Позиция {rank}">#{rank}</span> '
            f"<strong>{title}</strong>"
            f"<span>{subtitle}</span>"
            "</a>"
            "</li>"
        )
    return (
        '<section class="seo-ranking">'
        f"<h2>{html.escape(heading)}</h2>"
        f"<ol>{''.join(rows)}</ol>"
        "</section>"
    )


def home_prerender(feed: dict) -> str:
    """Semantic snapshot of the same live rankings consumed by React."""
    sections = [_ranking(feed.get("global", []), "Глобальный рейтинг")]
    for group in feed.get("top3", []):
        category = group.get("category", {})
        sections.append(
            _ranking(group.get("items", []), f"Топ-3: {category.get('label', '')}")
        )
    week = html.escape(str(feed.get("weekStart") or ""))
    return (
        '<div class="seo-prerender">'
        '<header><a href="/">В ЧАРТЕ</a>'
        '<nav aria-label="Категории">'
        '<a href="/category/music">Музыка</a>'
        '<a href="/category/movies">Фильмы</a>'
        '<a href="/category/games">Игры</a>'
        '<a href="/category/streamers">Стримеры</a>'
        "</nav></header>"
        '<main><h1>Всё, что сейчас обсуждают — в одной ленте</h1>'
        f'<p>Актуальные рейтинги за неделю <time datetime="{week}">{week}</time>.</p>'
        f"{''.join(sections)}"
        "</main></div>"
    )


def category_prerender(category: str, label: str, ranking: dict) -> str:
    week = html.escape(str(ranking.get("weekStart") or ""))
    items = ranking.get("items", [])
    return (
        '<div class="seo-prerender">'
        '<header><a href="/">В ЧАРТЕ</a></header>'
        f'<main><h1>{html.escape(label)}</h1>'
        f'<p>Рейтинг за неделю <time datetime="{week}">{week}</time>.</p>'
        f'{_ranking(items, f"Рейтинг: {label}")}'
        '<p><a href="/">Все категории рейтинга</a></p>'
        "</main></div>"
    )


def trend_prerender(item: dict) -> str:
    title = html.escape(str(item.get("title", "")))
    subtitle = html.escape(str(item.get("subtitle", "")))
    category = html.escape(str(item.get("categoryLabel", "")))
    category_id = html.escape(str(item.get("sphere", "")), quote=True)
    raw_rank = item.get("rank")
    raw_peak = item.get("peak")
    rank = "Вне чарта" if raw_rank is None else f"#{html.escape(str(raw_rank))}"
    peak = "—" if raw_peak is None else f"#{html.escape(str(raw_peak))}"
    weeks = html.escape(str(item.get("weeks", "—")))
    history_rows = []
    for point in item.get("history", []):
        week = html.escape(str(point.get("weekStart", "")))
        point_rank = point.get("rank")
        rank_text = "вне чарта" if point_rank is None else f"место {point_rank}"
        history_rows.append(
            f'<li><time datetime="{week}">{week}</time>: {html.escape(rank_text)}</li>'
        )
    history = (
        '<section><h2>История позиций</h2>'
        f'<ol>{"".join(history_rows)}</ol></section>'
        if history_rows
        else ""
    )
    return (
        '<div class="seo-prerender"><header><a href="/">В ЧАРТЕ</a></header><main>'
        f'<p><a href="/category/{category_id}">{category}</a></p>'
        f"<h1>{title}</h1><p>{subtitle}</p>"
        '<dl class="seo-trend-stats">'
        f"<dt>Текущая позиция</dt><dd>{rank}</dd>"
        f"<dt>Лучшее место</dt><dd>{peak}</dd>"
        f"<dt>Недель в рейтинге</dt><dd>{weeks}</dd>"
        "</dl>"
        f"{history}"
        f'<p><a href="/category/{category_id}">Вернуться в рейтинг «{category}»</a></p>'
        "</main></div>"
    )


def _page_html(
    index_html: str,
    *,
    body: str,
    title: str,
    description: str,
    canonical: str,
    initial_data: dict,
    image: str | None = None,
) -> str:
    marker = '<div id="root"></div>'
    if marker not in index_html:
        raise ValueError("Vite index.html does not contain the root marker")
    index_html = _metadata(
        index_html,
        title=title,
        description=description,
        canonical=canonical,
        image=image,
    )
    index_html = index_html.replace(marker, f'<div id="root">{body}</div>', 1)
    return index_html.replace(
        "</body>", f"  {_initial_data_script(initial_data)}\n  </body>", 1
    )


def spa_html(index_html: str, feed: dict | None = None) -> str:
    """Return the Vite shell, optionally with a real home-page snapshot."""
    marker = '<div id="root"></div>'
    if marker not in index_html:
        raise ValueError("Vite index.html does not contain the root marker")
    if feed is None:
        return index_html
    return _page_html(
        index_html,
        body=home_prerender(feed),
        title="Актуальные рейтинги музыки, фильмов, игр и стримеров | В ЧАРТЕ",
        description=(
            "Актуальные российские рейтинги музыки, фильмов, игр и стримеров. "
            "Позиции, изменения за неделю и история популярности."
        ),
        canonical=f"{SITE_URL}/",
        initial_data={"/feed": feed},
    )


def category_html(index_html: str, category: str, label: str, ranking: dict) -> str:
    title, description = CATEGORY_META[category]
    api_path = f"/categories/{category}/trends?sort=popular&limit=100"
    return _page_html(
        index_html,
        body=category_prerender(category, label, ranking),
        title=title,
        description=description,
        canonical=f"{SITE_URL}/category/{category}",
        initial_data={api_path: ranking},
    )


def trend_html(index_html: str, item: dict, week=None) -> str:
    title = str(item.get("title", ""))
    subtitle = str(item.get("subtitle", "")).strip()
    category = str(item.get("categoryLabel", ""))
    rank = item.get("rank")
    rank_text = f"место #{rank}" if rank is not None else "вне чарта"
    peak = item.get("peak")
    peak_text = f"#{peak}" if peak is not None else "—"
    description = (
        f"{title}: {rank_text} в рейтинге «{category}», "
        f"лучшее место {peak_text}, недель в рейтинге: {item.get('weeks', '—')}."
    )
    trend_id = int(item["key"])
    return _page_html(
        index_html,
        body=trend_prerender(item),
        title=(
            f"{title} — {subtitle} — популярность и история | В ЧАРТЕ"
            if subtitle
            else f"{title} — популярность, место в рейтинге и история | В ЧАРТЕ"
        ),
        description=description,
        canonical=f"{SITE_URL}/trend/{trend_id}",
        initial_data={
            f"/trends/{trend_id}{f'?week={week.isoformat()}' if week else ''}": item
        },
        image=item.get("cover"),
    )
