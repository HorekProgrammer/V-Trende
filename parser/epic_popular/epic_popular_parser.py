import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


GRAPHQL_URL = "https://store.epicgames.com/graphql"
CHART_SIZE = 50

QUERY = """
query collectionLayoutQuery($locale: String, $slug: String) {
  Storefront {
    collectionLayout(locale: $locale, slug: $slug) {
      collectionOffers {
        title
        id
        namespace
        catalogNs {
          mappings(pageType: "productHome") {
            pageSlug
          }
        }
      }
    }
  }
}
"""


def _fetch_payload(timeout):
    payload = {
        "query": QUERY,
        "variables": {
            "locale": "ru",
            "slug": "most-popular",
        },
    }

    request = Request(
        GRAPHQL_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/153.0.0.0 Safari/537.36"
            ),
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": (
                "https://store.epicgames.com/"
                "collection/most-popular?lang=ru"
            ),
            "Origin": "https://store.epicgames.com",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(
                response.read().decode("utf-8")
            )
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(
            "Epic Games Most Popular request failed"
        ) from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "Epic Games returned invalid JSON"
        ) from exc


def _extract_slug(offer):
    catalog = offer.get("catalogNs") or {}
    mappings = catalog.get("mappings") or []

    if not mappings:
        return None

    slug = mappings[0].get("pageSlug")
    return slug if isinstance(slug, str) and slug else None


def _parse_chart(payload):
    try:
        offers = (
            payload["data"]["Storefront"]
            ["collectionLayout"]["collectionOffers"]
        )
    except (KeyError, TypeError) as exc:
        raise RuntimeError(
            "Epic Games Most Popular data is missing"
        ) from exc

    if len(offers) != CHART_SIZE:
        raise RuntimeError(
            f"Expected {CHART_SIZE} games, got {len(offers)}"
        )

    result = []
    seen_ids = set()

    for position, offer in enumerate(offers, start=1):
        title = offer.get("title")
        offer_id = offer.get("id")
        namespace = offer.get("namespace")

        if not title or not offer_id or not namespace:
            raise RuntimeError(
                f"Epic Games item #{position} is incomplete"
            )

        if offer_id in seen_ids:
            raise RuntimeError(
                "Epic Games chart contains duplicate offers"
            )

        seen_ids.add(offer_id)

        result.append(
            {
                "position": position,
                "title": title.strip(),
                "epic_offer_id": offer_id,
                "epic_namespace": namespace,
                "epic_slug": _extract_slug(offer),
            }
        )

    return result


def get_epic_popular_chart(
    limit=None,
    timeout=30,
):
    if limit is not None and (
        isinstance(limit, bool)
        or not isinstance(limit, int)
        or limit <= 0
    ):
        raise ValueError(
            "limit must be a positive integer or None"
        )

    payload = _fetch_payload(timeout)
    chart = _parse_chart(payload)

    if limit is not None:
        return chart[:limit]

    return chart