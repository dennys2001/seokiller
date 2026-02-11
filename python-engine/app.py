import json
import os
import re
from urllib.parse import urljoin, urlparse

from dotenv import load_dotenv
import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify, request

# Load environment variables from .env if present (before importing modules that read env)
load_dotenv()

from content_generator import generate_aeo_content
from browser_fetch import fetch_html_with_playwright, is_bot_challenge, playwright_enabled
from crawler_async import crawl_site
from schema_builder import build_schema


DEFAULT_REQUEST_TIMEOUT = int(os.getenv("ENGINE_REQUEST_TIMEOUT", "180"))


def fetch_html(target_url: str, timeout: int = DEFAULT_REQUEST_TIMEOUT):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        )
    }
    try:
        resp = requests.get(target_url, headers=headers, timeout=timeout, allow_redirects=True)
        resp.raise_for_status()
        ctype = resp.headers.get("Content-Type", "").lower()
        if "text/html" not in ctype and "application/xhtml+xml" not in ctype:
            raise ValueError(f"Unsupported content type: {ctype}")
        if is_bot_challenge(resp.text) and playwright_enabled():
            return fetch_html_with_playwright(target_url, timeout=timeout)
        return resp.text, resp.url
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response is not None else None
        if status in (403, 429) and playwright_enabled():
            return fetch_html_with_playwright(target_url, timeout=timeout)
        raise


def normalize_url(base: str, link: str) -> str:
    try:
        return urljoin(base, link)
    except Exception:
        return link


def extract_basic(soup: BeautifulSoup):
    title = (soup.title.string or "").strip() if soup.title and soup.title.string else None
    desc_tag = soup.find("meta", attrs={"name": "description"})
    description = (desc_tag.get("content") or "").strip() if desc_tag else None
    h1 = [h.get_text(strip=True) for h in soup.find_all("h1")]
    h2 = [h.get_text(strip=True) for h in soup.find_all("h2")]
    return {
        "title": title,
        "description": description,
        "descriptionLength": len(description) if description else 0,
        "h1": h1,
        "h2": h2,
    }


def extract_links(soup: BeautifulSoup, final_url: str):
    parsed_base = urlparse(final_url)
    base_host = parsed_base.netloc.lower()
    internals = []
    externals = []
    for a in soup.find_all("a"):
        href = a.get("href")
        if not href:
            continue
        href = normalize_url(final_url, href)
        p = urlparse(href)
        if not p.scheme.startswith("http"):
            continue
        if p.netloc.lower() == base_host:
            internals.append(href)
        else:
            externals.append(href)

    def dedupe(lst):
        seen = set()
        out = []
        for x in lst:
            if x not in seen:
                seen.add(x)
                out.append(x)
        return out

    return {
        "internal": dedupe(internals)[:100],
        "external": dedupe(externals)[:100],
    }


def extract_images_issues(soup: BeautifulSoup):
    issues = []
    for img in soup.find_all("img"):
        alt = img.get("alt")
        if alt is None or str(alt).strip() == "":
            issues.append({"type": "images", "message": "Imagem sem atributo alt"})
    return issues


def extract_structured_data(soup: BeautifulSoup):
    ldjson_raw = []
    for s in soup.find_all("script", type=lambda t: t and "ld+json" in t):
        try:
            data = json.loads(s.string or "{}")
            ldjson_raw.append(data)
        except Exception:
            continue

    hreflang = [
        (l.get("hreflang"), normalize_url("", l.get("href", "")))
        for l in soup.find_all("link", rel=lambda r: r and "alternate" in r)
        if l.get("hreflang")
    ]

    og_locale = None
    og = soup.find("meta", property="og:locale")
    if og:
        og_locale = og.get("content")

    geo_meta = {}
    for name in ["geo.region", "geo.position", "ICBM"]:
        tag = soup.find("meta", attrs={"name": name})
        if tag and tag.get("content"):
            geo_meta[name] = tag.get("content")

    types = []

    def walk(node):
        if isinstance(node, list):
            for n in node:
                walk(n)
            return
        if isinstance(node, dict):
            t = node.get("@type")
            if isinstance(t, list):
                tlist = [str(x) for x in t]
            elif t:
                tlist = [str(t)]
            else:
                tlist = []
            for tt in tlist:
                types.append(tt)
            for v in node.values():
                walk(v)

    for d in ldjson_raw:
        walk(d)

    has_faq = any(t.lower() == "faqpage" for t in types)
    has_local_business = any("localbusiness" in t.lower() for t in types)

    return {
        "ldjsonTypes": types[:50],
        "hreflang": hreflang[:50],
        "ogLocale": og_locale,
        "geoMeta": geo_meta,
        "hasFAQ": has_faq,
        "hasLocalBusiness": has_local_business,
    }


def extract_question_headings(soup: BeautifulSoup):
    q_heads = []
    for tag in soup.find_all(["h1", "h2", "h3"]):
        text = tag.get_text(strip=True)
        if text and text.endswith("?"):
            q_heads.append(text)
    return q_heads[:20]


def compute_score(basic, struct, images_issues):
    score = 100
    issues = []

    if not basic.get("title"):
        score -= 15
        issues.append({"type": "meta", "message": "Titulo ausente"})
    else:
        tlen = len(basic["title"]) if basic.get("title") else 0
        if tlen < 10 or tlen > 65:
            score -= 5
            issues.append({"type": "meta", "message": "Comprimento do titulo nao ideal"})

    if not basic.get("description"):
        score -= 10
        issues.append({"type": "meta", "message": "Meta description ausente"})
    else:
        dlen = basic.get("descriptionLength", 0)
        if dlen < 80 or dlen > 160:
            score -= 5
            issues.append({"type": "meta", "message": "Comprimento da meta description nao ideal"})

    if not basic.get("h1"):
        score -= 8
        issues.append({"type": "content", "message": "H1 ausente"})

    if len(basic.get("h2", [])) < 1:
        score -= 3
        issues.append({"type": "content", "message": "Poucos subtitulos (H2)"})

    if images_issues:
        score -= min(10, len(images_issues))
        issues.extend(images_issues)

    if not struct.get("hreflang") and not struct.get("ogLocale"):
        score -= 4
        issues.append({"type": "geo", "message": "Sinal de localizacao/idioma ausente (hreflang/og:locale)"})

    if not struct.get("hasLocalBusiness"):
        issues.append({"type": "geo", "message": "Schema LocalBusiness nao detectado"})

    if not struct.get("hasFAQ"):
        issues.append({"type": "aeo", "message": "Schema FAQPage nao detectado"})

    score = max(0, min(100, score))
    return score, issues


def generate_recommendations(url, basic, q_heads):
    title = basic.get("title") or ""
    if not title:
        host = urlparse(url).hostname or "Seu Site"
        title_suggest = f"{host} | Guia completo e dicas"
    else:
        title_suggest = title[:65]

    desc = basic.get("description") or ""
    if not desc:
        desc_suggest = (
            "Resumo claro do conteudo da pagina com foco na intencao do usuario, "
            "palavras-chave principais e proposta de valor (120-155 caracteres)."
        )
    else:
        desc_suggest = desc[:155]

    if q_heads:
        faq_lines = ["Perguntas Frequentes:"] + [f"- {q}" for q in q_heads[:6]]
    else:
        faq_lines = [
            "Perguntas Frequentes:",
            "- O que e este servico?",
            "- Quais beneficios principais?",
            "- Como funciona o atendimento?",
        ]

    optimized = (
        f"Titulo sugerido: {title_suggest}\n\n"
        f"Meta description sugerida: {desc_suggest}\n\n"
        "Sugestoes AEO (estrutura de respostas/FAQ):\n"
        + "\n".join(faq_lines)
    )
    return optimized


def build_files(url, basic, links, score, issues):
    files = []
    files.append(
        {
            "filename": "summary.json",
            "mimeType": "application/json",
            "data": {
                "url": url,
                "score": score,
                "issues": issues,
            },
        }
    )
    files.append(
        {
            "filename": "headings.json",
            "mimeType": "application/json",
            "data": {
                "title": basic.get("title"),
                "h1": basic.get("h1", []),
                "h2": basic.get("h2", []),
            },
        }
    )
    files.append(
        {
            "filename": "meta.json",
            "mimeType": "application/json",
            "data": {
                "description": basic.get("description"),
                "descriptionLength": basic.get("descriptionLength", 0),
            },
        }
    )
    files.append(
        {
            "filename": "links.json",
            "mimeType": "application/json",
            "data": {
                "internal": links.get("internal", []),
                "external": links.get("external", []),
            },
        }
    )
    return files


def safe_filename(url: str):
    safe = url.replace("https://", "").replace("http://", "")
    safe = re.sub(r"[^a-zA-Z0-9\\-_]", "_", safe)
    return safe[:120] or "pagina"


app = Flask(__name__)


@app.post("/analyze")
def analyze():
    body = request.get_json(silent=True) or {}
    url = (body.get("url") or "").strip()
    use_crawler = bool(body.get("useCrawler"))

    if not url:
        return jsonify({"status": "error", "message": "Campo 'url' e obrigatorio"}), 400

    try:
        if use_crawler:
            max_pages = int(body.get("maxPages") or 15)
            max_tasks = int(body.get("maxTasks") or 6)
            delay = float(body.get("delay") or 0.4)
            timeout = int(body.get("timeout") or DEFAULT_REQUEST_TIMEOUT)

            pages = crawl_site(url, max_pages=max_pages, max_tasks=max_tasks, delay=delay, timeout=timeout)
            results = []
            files = []
            for page in pages:
                aeo = generate_aeo_content(page)
                schema_json = build_schema(aeo, page)
                safe = safe_filename(page.get("url", url))
                results.append(
                    {
                        "url": page.get("url"),
                        "title": page.get("title"),
                        "h1": page.get("h1"),
                        "markdown": aeo.get("markdown"),
                        "schema": json.loads(schema_json),
                    }
                )
                files.append(
                    {
                        "filename": f"{safe}.md",
                        "mimeType": "text/markdown",
                        "data": aeo.get("markdown"),
                    }
                )
                files.append(
                    {
                        "filename": f"{safe}.json",
                        "mimeType": "application/json",
                        "data": json.loads(schema_json),
                    }
                )

            if results:
                primary = results[0]
                basic = {
                    "title": primary.get("title"),
                    "description": None,
                    "descriptionLength": 0,
                    "h1": [primary.get("h1")] if primary.get("h1") else [],
                    "h2": [],
                }
                struct = {
                    "hreflang": [],
                    "ogLocale": None,
                    "geoMeta": {},
                    "hasFAQ": False,
                    "hasLocalBusiness": False,
                }
                score, issues = compute_score(basic, struct, [])
                files.extend(build_files(primary.get("url") or url, basic, {"internal": [], "external": []}, score, issues))

            return jsonify(
                {
                    "analyzedUrl": url,
                    "mode": "crawler",
                    "pagesProcessed": len(results),
                    "optimizedContent": "\n\n".join([r.get("markdown", "") for r in results]),
                    "files": files,
                    "pages": results,
                }
            )

        html, final_url = fetch_html(url)
        soup = BeautifulSoup(html, "html.parser")

        basic = extract_basic(soup)
        links = extract_links(soup, final_url)
        images_issues = extract_images_issues(soup)
        struct = extract_structured_data(soup)
        q_heads = extract_question_headings(soup)
        score, issues = compute_score(basic, struct, images_issues)

        optimized_content = generate_recommendations(final_url, basic, q_heads)
        summary_text = (
            f"Analise concluida para {final_url}. "
            f"Titulo {'presente' if basic.get('title') else 'ausente'}, "
            f"meta description {'presente' if basic.get('description') else 'ausente'}, "
            f"{len(basic.get('h2', []))} H2 encontrados. Score: {score}."
        )

        files = build_files(final_url, basic, links, score, issues)

        return jsonify(
            {
                "analyzedUrl": final_url,
                "summary": summary_text,
                "optimizedContent": optimized_content,
                "files": files,
            }
        )

    except requests.exceptions.RequestException as e:
        return jsonify({"status": "error", "message": f"Falha ao buscar URL: {str(e)}"}), 502
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == "__main__":
    port = int(os.getenv("ENGINE_PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
