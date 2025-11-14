import os
import re
import json
from urllib.parse import urlparse, urljoin

import requests
from bs4 import BeautifulSoup
from flask import Flask, request, jsonify


def fetch_html(target_url: str, timeout: int = 15):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        )
    }
    resp = requests.get(target_url, headers=headers, timeout=timeout, allow_redirects=True)
    resp.raise_for_status()
    ctype = resp.headers.get("Content-Type", "").lower()
    if "text/html" not in ctype and "application/xhtml+xml" not in ctype:
        raise ValueError(f"Unsupported content type: {ctype}")
    return resp.text, resp.url


def normalize_url(base: str, link: str) -> str:
    try:
        return urljoin(base, link)
    except Exception:
        return link


def extract_basic(soup: BeautifulSoup):
    title = (soup.title.string or "").strip() if soup.title and soup.title.string else None
    # Meta description
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
    # Deduplicate and limit
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
            issues.append({
                "type": "images",
                "message": "Imagem sem atributo alt",
            })
    return issues


def extract_structured_data(soup: BeautifulSoup):
    # Detect common structured data and hreflang/locale for GEO/AEO hints
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

    # Quick markers
    has_faq = False
    has_local_business = False
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
                if tt.lower() == "faqpage":
                    has_faq = True  # noqa: F841
                if "localbusiness" in tt.lower():
                    has_local_business = True  # noqa: F841
            for v in node.values():
                walk(v)

    for d in ldjson_raw:
        walk(d)

    # Re-evaluate booleans after traversal
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
        if not text:
            continue
        if text.endswith("?"):
            q_heads.append(text)
    return q_heads[:20]


def compute_score(basic, struct, images_issues):
    score = 100
    issues = []

    if not basic.get("title"):
        score -= 15
        issues.append({"type": "meta", "message": "Título ausente"})
    else:
        tlen = len(basic["title"]) if basic.get("title") else 0
        if tlen < 10 or tlen > 65:
            score -= 5
            issues.append({"type": "meta", "message": "Comprimento do título não ideal"})

    if not basic.get("description"):
        score -= 10
        issues.append({"type": "meta", "message": "Meta description ausente"})
    else:
        dlen = basic.get("descriptionLength", 0)
        if dlen < 80 or dlen > 160:
            score -= 5
            issues.append({"type": "meta", "message": "Comprimento da meta description não ideal"})

    if not basic.get("h1"):
        score -= 8
        issues.append({"type": "content", "message": "H1 ausente"})

    # H2 usability
    if len(basic.get("h2", [])) < 1:
        score -= 3
        issues.append({"type": "content", "message": "Poucos subtítulos (H2)"})

    # Image alts
    if images_issues:
        score -= min(10, len(images_issues))
        issues.extend(images_issues)

    # GEO markers
    if not struct.get("hreflang") and not struct.get("ogLocale"):
        score -= 4
        issues.append({"type": "geo", "message": "Sinal de localização/idioma ausente (hreflang/og:locale)"})

    if not struct.get("hasLocalBusiness"):
        issues.append({"type": "geo", "message": "Schema LocalBusiness não detectado"})

    # AEO markers
    if not struct.get("hasFAQ"):
        issues.append({"type": "aeo", "message": "Schema FAQPage não detectado"})

    # Clamp score
    score = max(0, min(100, score))
    return score, issues


def generate_recommendations(url, basic, q_heads):
    # Title suggestion
    title = basic.get("title") or ""
    if not title:
        # fall back: hostname-based
        host = urlparse(url).hostname or "Seu Site"
        title_suggest = f"{host} — Guia Completo e Dicas"
    else:
        title_suggest = title[:65]

    # Meta description suggestion
    desc = basic.get("description") or ""
    if not desc:
        # fallback: generic prompt
        desc_suggest = (
            "Resumo claro do conteúdo da página com foco na intenção do usuário, "
            "palavras-chave principais e proposta de valor (120–155 caracteres)."
        )
    else:
        desc_suggest = desc[:155]

    # AEO suggestions: convert question headings into Q&A outline
    if q_heads:
        faq_lines = ["Perguntas Frequentes:"] + [f"- {q}" for q in q_heads[:6]]
    else:
        faq_lines = [
            "Perguntas Frequentes:",
            "- O que é este serviço?",
            "- Quais benefícios principais?",
            "- Como funciona o atendimento?",
        ]

    optimized = (
        f"Título sugerido: {title_suggest}\n\n"
        f"Meta description sugerida: {desc_suggest}\n\n"
        "Sugestões AEO (estrutura de respostas/FAQ):\n"
        + "\n".join(faq_lines)
    )
    return optimized


def build_files(url, basic, links, score, issues):
    files = []
    files.append({
        "filename": "summary.json",
        "mimeType": "application/json",
        "data": {
            "url": url,
            "score": score,
            "issues": issues,
        },
    })
    files.append({
        "filename": "headings.json",
        "mimeType": "application/json",
        "data": {
            "title": basic.get("title"),
            "h1": basic.get("h1", []),
            "h2": basic.get("h2", []),
        },
    })
    files.append({
        "filename": "meta.json",
        "mimeType": "application/json",
        "data": {
            "description": basic.get("description"),
            "descriptionLength": basic.get("descriptionLength", 0),
        },
    })
    files.append({
        "filename": "links.json",
        "mimeType": "application/json",
        "data": {
            "internal": links.get("internal", []),
            "external": links.get("external", []),
        },
    })
    return files


app = Flask(__name__)


@app.post("/analyze")
def analyze():
    body = request.get_json(silent=True) or {}
    url = (body.get("url") or "").strip()
    if not url:
        return jsonify({"status": "error", "message": "Campo 'url' é obrigatório"}), 400

    try:
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
            f"Análise concluída para {final_url}. "
            f"Título {'presente' if basic.get('title') else 'ausente'}, "
            f"meta description {'presente' if basic.get('description') else 'ausente'}, "
            f"{len(basic.get('h2', []))} H2 encontrados. Score: {score}."
        )

        files = build_files(final_url, basic, links, score, issues)

        return jsonify({
            "analyzedUrl": final_url,
            "summary": summary_text,
            "optimizedContent": optimized_content,
            "files": files,
        })

    except requests.exceptions.RequestException as e:
        return jsonify({"status": "error", "message": f"Falha ao buscar URL: {str(e)}"}), 502
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == "__main__":
    port = int(os.getenv("ENGINE_PORT", "5000"))
    app.run(host="0.0.0.0", port=port)

