"""Low-concurrency audit of every indexable URL in the production Sitemap."""

from __future__ import annotations

import argparse
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
from xml.etree import ElementTree


USER_AGENT = "VCharte-SEO-Audit/1.0 (+https://vcharte.com/robots.txt)"


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self.h1: list[str] = []
        self.description = ""
        self.canonical = ""
        self.links: list[str] = []
        self.noindex = False
        self.og_title = ""
        self.og_description = ""
        self.og_url = ""
        self._capture: str | None = None

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag in {"title", "h1"}:
            self._capture = tag
            if tag == "h1":
                self.h1.append("")
        elif tag == "meta":
            name = values.get("name", "").lower()
            property_name = values.get("property", "").lower()
            if name == "description":
                self.description = values.get("content", "")
            if name == "robots" and "noindex" in values.get("content", "").lower():
                self.noindex = True
            if property_name == "og:title":
                self.og_title = values.get("content", "")
            elif property_name == "og:description":
                self.og_description = values.get("content", "")
            elif property_name == "og:url":
                self.og_url = values.get("content", "")
        elif tag == "link" and values.get("rel", "").lower() == "canonical":
            self.canonical = values.get("href", "")
        elif tag == "a" and values.get("href"):
            self.links.append(values["href"])

    def handle_endtag(self, tag):
        if tag == self._capture:
            self._capture = None

    def handle_data(self, data):
        if self._capture == "title":
            self.title += data
        elif self._capture == "h1" and self.h1:
            self.h1[-1] += data


@dataclass
class Result:
    url: str
    status: int | None
    content_type: str
    title: str
    canonical: str
    h1: list[str]
    internal_links: int
    elapsed_ms: int
    issues: list[str]


def fetch(url: str, timeout: float) -> tuple[int, str, bytes]:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=timeout) as response:
        return response.status, response.headers.get("Content-Type", ""), response.read()


def audit_url(url: str, timeout: float, indexable_urls: frozenset[str]) -> Result:
    started = time.monotonic()
    issues: list[str] = []
    status = None
    content_type = ""
    parser = PageParser()
    try:
        status, content_type, body = fetch(url, timeout)
        if status != 200:
            issues.append(f"HTTP {status}")
        if "text/html" not in content_type.lower():
            issues.append(f"Content-Type {content_type or 'missing'}")
        text = body.decode("utf-8", errors="replace")
        parser.feed(text)
        if len(parser.h1) != 1 or not parser.h1[0].strip():
            issues.append(f"expected one H1, got {len(parser.h1)}")
        if not parser.title.strip():
            issues.append("missing title")
        if not parser.description.strip():
            issues.append("missing meta description")
        if parser.canonical != url:
            issues.append(f"canonical mismatch: {parser.canonical or 'missing'}")
        if not parser.og_title or not parser.og_description:
            issues.append("Open Graph title/description missing")
        if parser.og_url != url:
            issues.append(f"Open Graph URL mismatch: {parser.og_url or 'missing'}")
        if parser.noindex or "noindex" in text.lower():
            issues.append("noindex")
        if "data-state--error" in text or "Не удалось загрузить данные" in text:
            issues.append("React error state")
        if '<div id="root"></div>' in text:
            issues.append("empty React root")
        internal = [
            urljoin(url, link)
            for link in parser.links
            if urlparse(urljoin(url, link)).netloc == "vcharte.com"
        ]
        if not internal:
            issues.append("no internal links")
        broken_targets = sorted({link for link in internal if link not in indexable_urls})
        if broken_targets:
            issues.append(f"links outside Sitemap: {', '.join(broken_targets[:3])}")
        if urlparse(url).path.startswith("/category/") and "/trend/" not in " ".join(internal):
            issues.append("category has no trend links")
        if urlparse(url).path.startswith("/trend/"):
            required_facts = ("Текущая позиция", "Лучшее место", "Недель в рейтинге")
            if any(fact not in text for fact in required_facts):
                issues.append("trend facts missing")
    except HTTPError as error:
        status = error.code
        content_type = error.headers.get("Content-Type", "")
        issues.append(f"HTTP {error.code}")
    except (URLError, TimeoutError, OSError) as error:
        issues.append(f"request failed: {error}")
    return Result(
        url=url,
        status=status,
        content_type=content_type,
        title=parser.title.strip(),
        canonical=parser.canonical,
        h1=[value.strip() for value in parser.h1],
        internal_links=len(parser.links),
        elapsed_ms=round((time.monotonic() - started) * 1000),
        issues=issues,
    )


def sitemap_urls(sitemap_url: str, timeout: float) -> list[str]:
    status, content_type, body = fetch(sitemap_url, timeout)
    if status != 200 or "xml" not in content_type.lower():
        raise RuntimeError(f"Invalid Sitemap response: {status} {content_type}")
    root = ElementTree.fromstring(body)
    namespace = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    urls = [node.text for node in root.findall("s:url/s:loc", namespace) if node.text]
    if len(urls) != len(set(urls)):
        raise RuntimeError("Sitemap contains duplicate URLs")
    return urls


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sitemap", default="https://vcharte.com/sitemap.xml")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--timeout", type=float, default=20)
    parser.add_argument("--output")
    args = parser.parse_args()
    if not 1 <= args.workers <= 8:
        parser.error("--workers must be between 1 and 8")

    urls = sitemap_urls(args.sitemap, args.timeout)
    indexable_urls = frozenset(urls)
    results: list[Result] = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(audit_url, url, args.timeout, indexable_urls): url
            for url in urls
        }
        for future in as_completed(futures):
            results.append(future.result())
    results.sort(key=lambda result: result.url)
    for field in ("title", "canonical"):
        values: dict[str, list[Result]] = {}
        for result in results:
            value = getattr(result, field)
            if value:
                values.setdefault(value, []).append(result)
        for value, matches in values.items():
            if len(matches) > 1:
                for result in matches:
                    result.issues.append(f"duplicate {field}: {value}")
    report = {
        "sitemap": args.sitemap,
        "checked": len(results),
        "valid": sum(not result.issues for result in results),
        "invalid": sum(bool(result.issues) for result in results),
        "results": [asdict(result) for result in results],
    }
    output = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as file:
            file.write(output + "\n")
    print(f"Checked: {report['checked']}; valid: {report['valid']}; invalid: {report['invalid']}")
    for result in results:
        if result.issues:
            print(f"FAIL {result.url}: {'; '.join(result.issues)}")
    return 1 if report["invalid"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
