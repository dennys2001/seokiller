import json
import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


BOILERPLATE_TAGS = ("nav", "footer", "aside", "script", "style", "noscript")


def _clean_text(value: str) -> str:
    return " ".join((value or "").split())


def _extract_breadcrumbs(soup: BeautifulSoup, base_url: str):
    crumbs = []
    selectors = [
        "nav[aria-label*='breadcrumb' i] a",
        ".breadcrumb a",
        "[itemtype*='BreadcrumbList'] a",
    ]
    for selector in selectors:
        for anchor in soup.select(selector):
            label = _clean_text(anchor.get_text(" ", strip=True))
            href = urljoin(base_url, anchor.get("href") or "")
            if label and href:
                crumbs.append({"name": label, "url": href})

    deduped = []
    seen = set()
    for crumb in crumbs:
        key = (crumb["name"], crumb["url"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(crumb)
    return deduped[:20]


def _extract_structured_data_raw(soup: BeautifulSoup):
    raw = []
    for script in soup.find_all("script", type=lambda value: value and "ld+json" in value):
        text = (script.string or script.get_text() or "").strip()
        if not text:
            continue
        try:
            raw.append(json.loads(text))
        except Exception:
            continue
    return raw


def parse_page(html: str, final_url: str):
    soup = BeautifulSoup(html, "html.parser")

    title = _clean_text(soup.title.get_text(" ", strip=True) if soup.title else "")
    desc_tag = soup.find("meta", attrs={"name": "description"})
    meta_description = _clean_text(desc_tag.get("content") if desc_tag else "")

    for tag in soup.find_all(BOILERPLATE_TAGS):
        tag.decompose()

    main = soup.find("main") or soup.find("article") or soup.body or soup

    headings = {
        "h1": [_clean_text(node.get_text(" ", strip=True)) for node in main.find_all("h1") if _clean_text(node.get_text(" ", strip=True))],
        "h2": [_clean_text(node.get_text(" ", strip=True)) for node in main.find_all("h2") if _clean_text(node.get_text(" ", strip=True))],
        "h3": [_clean_text(node.get_text(" ", strip=True)) for node in main.find_all("h3") if _clean_text(node.get_text(" ", strip=True))],
    }

    paragraphs = [_clean_text(node.get_text(" ", strip=True)) for node in main.find_all("p")]
    paragraphs = [value for value in paragraphs if value]

    lists = []
    for node in main.find_all(["ul", "ol"]):
        items = [_clean_text(li.get_text(" ", strip=True)) for li in node.find_all("li")]
        items = [item for item in items if item]
        if items:
            lists.append(items[:20])
    lists = lists[:20]

    tables = []
    for table in main.find_all("table"):
        rows = []
        for row in table.find_all("tr"):
            cells = [_clean_text(col.get_text(" ", strip=True)) for col in row.find_all(["th", "td"])]
            cells = [cell for cell in cells if cell]
            if cells:
                rows.append(cells[:8])
        if rows:
            tables.append(rows[:20])
    tables = tables[:10]

    links = []
    base_host = urlparse(final_url).netloc.lower()
    for anchor in soup.find_all("a", href=True):
        href = urljoin(final_url, anchor["href"].strip())
        text = _clean_text(anchor.get_text(" ", strip=True))
        parsed = urlparse(href)
        if not parsed.scheme.startswith("http"):
            continue
        links.append(
            {
                "url": href,
                "anchor": text,
                "type": "internal" if parsed.netloc.lower() == base_host else "external",
            }
        )

    internal_links = [link for link in links if link["type"] == "internal"]
    external_links = [link for link in links if link["type"] == "external"]

    full_text = _clean_text(
        " ".join([title, meta_description, *headings["h1"], *headings["h2"], *paragraphs])
    )

    page_source_flags = {
        "has_hreflang": bool(soup.find("link", attrs={"rel": lambda value: value and "alternate" in value})),
    }

    return {
        "url": final_url,
        "title": title,
        "meta_description": meta_description,
        "headings": headings,
        "paragraphs": paragraphs,
        "lists": lists,
        "tables": tables,
        "breadcrumbs": _extract_breadcrumbs(soup, final_url),
        "structured_data_raw": _extract_structured_data_raw(soup),
        "internal_links": internal_links[:250],
        "external_links": external_links[:250],
        "full_text": full_text[:60000],
        "flags": page_source_flags,
    }


def expected_data_gaps(parsed_page):
    text = (parsed_page.get("full_text") or "").lower()
    gaps = []
    rules = [
        ("price", "Preco nao informado", ("preco", "r$", "valor", "a partir de")),
        ("versions", "Versoes nao informadas", ("versao", "versoes", "trim", "configuracao")),
        ("consumption", "Consumo nao informado", ("consumo", "km/l", "autonomia", "eficiencia")),
        ("warranty", "Garantia nao informada", ("garantia", "anos de garantia")),
    ]
    for field, message, hints in rules:
        if not any(hint in text for hint in hints):
            gaps.append({"field": field, "message": message})
    return gaps
