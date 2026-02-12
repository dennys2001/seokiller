import json
import os

from dotenv import load_dotenv
import requests
from flask import Flask, jsonify, request

from aeo_pipeline import (
    build_internal_link_graph,
    build_page_artifacts,
    build_summary_text,
    to_download_files,
)
from browser_fetch import is_unusable_page, fetch_html_with_playwright, playwright_enabled
from crawler_async import crawl_site
from entity_engine import aggregate_sitewide_entities
from parser_engine import parse_page


load_dotenv()

DEFAULT_REQUEST_TIMEOUT = int(os.getenv("ENGINE_REQUEST_TIMEOUT", "180"))


def fetch_html(
    target_url: str,
    timeout: int = DEFAULT_REQUEST_TIMEOUT,
    allow_unusable: bool = False,
):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        )
    }
    try:
        resp = requests.get(target_url, headers=headers, timeout=timeout, allow_redirects=True)
        status = resp.status_code
        ctype = resp.headers.get("Content-Type", "").lower()
        is_html = ("text/html" in ctype) or ("application/xhtml+xml" in ctype) or (ctype.strip() == "")
        if not is_html:
            if allow_unusable:
                return (
                    "<html><head><title>Conteudo indisponivel</title></head><body></body></html>",
                    resp.url,
                    True,
                )
            raise ValueError(f"Unsupported content type: {ctype}")

        # Treat common anti-bot / maintenance HTTP statuses as "unusable" (do not hard fail).
        if status >= 400:
            if status in (403, 429, 503) and playwright_enabled():
                html, final_url = fetch_html_with_playwright(target_url, timeout=timeout)
                if not is_unusable_page(html):
                    return html, final_url, False
                if allow_unusable:
                    return html, final_url, True
                raise ValueError("Conteudo bloqueado por anti-bot ou pagina de manutencao")
            if allow_unusable:
                return resp.text, resp.url, True
            if status in (403, 429, 503):
                raise ValueError("Conteudo bloqueado por anti-bot ou pagina de manutencao")
            resp.raise_for_status()

        if is_unusable_page(resp.text):
            if playwright_enabled():
                html, final_url = fetch_html_with_playwright(target_url, timeout=timeout)
                if is_unusable_page(html):
                    if allow_unusable:
                        return html, final_url, True
                    raise ValueError("Conteudo bloqueado por anti-bot ou pagina de manutencao")
                return html, final_url, False
            if allow_unusable:
                return resp.text, resp.url, True
            raise ValueError("Conteudo bloqueado por anti-bot ou pagina de manutencao")
        return resp.text, resp.url, False
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response is not None else None
        if status in (403, 429, 503) and playwright_enabled():
            html, final_url = fetch_html_with_playwright(target_url, timeout=timeout)
            if is_unusable_page(html):
                if allow_unusable:
                    return html, final_url, True
                raise ValueError("Conteudo bloqueado por anti-bot ou pagina de manutencao")
            return html, final_url, False
        raise


def _analysis_details(parsed_page, artifacts):
    return {
        "intent": artifacts["intent"],
        "primaryQuestion": artifacts["primary_question"],
        "secondaryQuestions": artifacts["secondary_questions"],
        "topEntities": artifacts["entities"][:10],
        "scoreBreakdown": artifacts["score_pack"]["breakdown"],
        "issuesByCategory": artifacts["issues_pack"],
        "testReport": artifacts["test_report"],
        "url": parsed_page.get("url"),
    }


def build_single_page_response(
    url: str,
    warning: str | None = None,
    mode: str = "single",
    allow_unusable: bool = False,
):
    html, final_url, unusable = fetch_html(url, allow_unusable=allow_unusable)
    if unusable and not warning:
        warning = (
            "Site protegido por anti-bot ou em manutencao. "
            "Nao foi possivel realizar analise completa; exibindo somente resumo."
        )
    parsed_page = parse_page(html, final_url)
    artifacts = build_page_artifacts(parsed_page)
    files = to_download_files(final_url, artifacts)
    response = {
        "analyzedUrl": final_url,
        "summary": build_summary_text(parsed_page, artifacts["score_pack"]),
        "optimizedContent": artifacts["content_pack"]["markdown"],
        "files": files,
        "analysisDetails": _analysis_details(parsed_page, artifacts),
        "mode": mode,
    }
    if warning:
        response["warning"] = warning
    return response


app = Flask(__name__)


@app.post("/analyze")
def analyze():
    body = request.get_json(silent=True) or {}
    url = (body.get("url") or "").strip()
    use_crawler = bool(body.get("useCrawler"))

    if not url:
        return jsonify({"status": "error", "message": "Campo 'url' e obrigatorio"}), 400

    try:
        if not use_crawler:
            return jsonify(build_single_page_response(url, mode="single"))

        max_pages = int(body.get("maxPages") or 15)
        max_tasks = int(body.get("maxTasks") or 6)
        delay = float(body.get("delay") or 0.4)
        timeout = int(body.get("timeout") or DEFAULT_REQUEST_TIMEOUT)

        crawled_pages = crawl_site(url, max_pages=max_pages, max_tasks=max_tasks, delay=delay, timeout=timeout)

        page_results = []
        all_files = []
        site_entities_input = []
        parsed_pages = []
        analysis_details = []
        for page in crawled_pages:
            html = page.get("html")
            page_url = page.get("url") or url
            if not html:
                continue
            parsed_page = parse_page(html, page_url)
            artifacts = build_page_artifacts(parsed_page)
            parsed_pages.append(parsed_page)
            site_entities_input.append({"url": parsed_page.get("url"), "entities": artifacts["entities"]})
            analysis_details.append(_analysis_details(parsed_page, artifacts))
            all_files.extend(to_download_files(parsed_page.get("url"), artifacts))
            page_results.append(
                {
                    "url": parsed_page.get("url"),
                    "title": parsed_page.get("title"),
                    "h1": parsed_page.get("headings", {}).get("h1", []),
                    "intent": artifacts["intent"],
                    "primaryQuestion": artifacts["primary_question"],
                    "score": artifacts["score_pack"]["total"],
                    "markdown": artifacts["content_pack"]["markdown"],
                    "schema": artifacts["schema"],
                }
            )

        if not page_results:
            fallback = build_single_page_response(
                url,
                warning=(
                    "Site protegido por anti-bot ou em manutencao. "
                    "Nao foi possivel realizar analise completa com crawler; exibindo somente resumo."
                ),
                mode="crawler_fallback_summary",
                allow_unusable=True,
            )
            fallback["pagesProcessed"] = 0
            return jsonify(fallback)

        entities_sitewide = aggregate_sitewide_entities(site_entities_input)
        link_graph = build_internal_link_graph(parsed_pages)
        all_files.append(
            {
                "filename": "entities_sitewide.json",
                "mimeType": "application/json",
                "data": entities_sitewide,
            }
        )
        all_files.append(
            {
                "filename": "internal_link_graph.json",
                "mimeType": "application/json",
                "data": link_graph,
            }
        )

        return jsonify(
            {
                "analyzedUrl": url,
                "mode": "crawler",
                "pagesProcessed": len(page_results),
                "optimizedContent": "\n\n".join([p.get("markdown", "") for p in page_results]),
                "files": all_files,
                "pages": page_results,
                "analysisDetails": analysis_details[0] if analysis_details else {},
                "entitiesSitewide": entities_sitewide[:20],
            }
        )
    except requests.exceptions.RequestException as e:
        return jsonify({"status": "error", "message": f"Falha ao buscar URL: {str(e)}"}), 502
    except ValueError as e:
        message = str(e)
        lowered = message.lower()
        if "anti-bot" in lowered or "manutencao" in lowered or "manuten" in lowered or "bloque" in lowered:
            # Never hard-fail on blocked pages: return a minimal, non-breaking summary with a warning.
            try:
                return jsonify(
                    build_single_page_response(
                        url,
                        warning=(
                            "Site protegido por anti-bot ou em manutencao. "
                            "Nao foi possivel realizar analise completa; exibindo somente resumo."
                        ),
                        mode="single_fallback_summary",
                        allow_unusable=True,
                    )
                )
            except Exception:
                return jsonify({"status": "error", "message": message}), 502
        return jsonify({"status": "error", "message": message}), 502
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == "__main__":
    port = int(os.getenv("ENGINE_PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
