import re
from collections import defaultdict

from content_generator_aeo import generate_aeo_markdown
from entity_engine import extract_entities
from intent_engine import detect_intent, infer_primary_question, infer_secondary_questions
from issue_engine import build_issues
from parser_engine import expected_data_gaps
from schema_engine import build_schema_ld, check_schema_parity
from scoring_engine import compute_aeo_score
from test_harness import run_test_harness


def safe_filename(url: str):
    safe = url.replace("https://", "").replace("http://", "")
    safe = re.sub(r"[^a-zA-Z0-9\-_]", "_", safe)
    return safe[:120] or "pagina"


def _extract_legacy_basic(parsed_page):
    return {
        "title": parsed_page.get("title"),
        "description": parsed_page.get("meta_description"),
        "descriptionLength": len(parsed_page.get("meta_description") or ""),
        "h1": parsed_page.get("headings", {}).get("h1", []),
        "h2": parsed_page.get("headings", {}).get("h2", []),
    }


def _legacy_links(parsed_page):
    return {
        "internal": [item.get("url") for item in parsed_page.get("internal_links", [])][:100],
        "external": [item.get("url") for item in parsed_page.get("external_links", [])][:100],
    }


def _legacy_summary_from_breakdown(score_pack, issues_pack):
    flat_issues = []
    for category, issues in issues_pack.items():
        for issue in issues:
            flat_issues.append({"type": category, "message": issue})
    return {"score": score_pack.get("total", 0), "issues": flat_issues}


def build_page_artifacts(parsed_page):
    intent = detect_intent(parsed_page.get("url"), parsed_page)
    primary_question = infer_primary_question(intent, parsed_page)
    secondary_questions = infer_secondary_questions(intent, parsed_page, limit=6)
    entities = extract_entities(parsed_page)
    gaps = expected_data_gaps(parsed_page)

    content_pack = generate_aeo_markdown(
        parsed_page=parsed_page,
        intent=intent,
        primary_question=primary_question,
        secondary_questions=secondary_questions,
        entities=entities,
        expected_gaps=gaps,
    )

    schema = build_schema_ld(parsed_page, content_pack, intent, entities)
    parity_ok, parity_errors = check_schema_parity(schema, content_pack)

    score_pack = compute_aeo_score(
        intent=intent,
        primary_question=primary_question,
        entities=entities,
        content_pack=content_pack,
        schema=schema,
        secondary_questions=secondary_questions,
    )

    content_pack["schema_graph"] = schema.get("@graph", [])

    issues_pack = build_issues(
        parsed_page=parsed_page,
        score_pack=score_pack,
        content_pack=content_pack,
        entities=entities,
        schema_parity_ok=parity_ok,
        schema_parity_errors=parity_errors,
        expected_gaps=gaps,
    )

    test_report = run_test_harness(primary_question, content_pack, entities, schema)

    page_meta = {
        "url": parsed_page.get("url"),
        "title": parsed_page.get("title"),
        "intent": intent,
        "primaryQuestion": primary_question,
        "secondaryQuestions": secondary_questions,
        "directAnswer": content_pack.get("direct_answer"),
        "sourceSummary": (parsed_page.get("paragraphs") or [""])[0][:300],
    }

    return {
        "intent": intent,
        "primary_question": primary_question,
        "secondary_questions": secondary_questions,
        "entities": entities,
        "content_pack": content_pack,
        "schema": schema,
        "score_pack": score_pack,
        "issues_pack": issues_pack,
        "test_report": test_report,
        "page_meta": page_meta,
        "legacy_basic": _extract_legacy_basic(parsed_page),
        "legacy_links": _legacy_links(parsed_page),
        "legacy_summary": _legacy_summary_from_breakdown(score_pack, issues_pack),
    }


def to_download_files(page_url: str, artifacts: dict):
    base = safe_filename(page_url)
    files = [
        {"filename": f"{base}_page.md", "mimeType": "text/markdown", "data": artifacts["content_pack"]["markdown"]},
        {"filename": f"{base}_page.json", "mimeType": "application/json", "data": artifacts["page_meta"]},
        {"filename": f"{base}_entities.json", "mimeType": "application/json", "data": artifacts["entities"]},
        {"filename": f"{base}_schema.json", "mimeType": "application/json", "data": artifacts["schema"]},
        {"filename": f"{base}_score.json", "mimeType": "application/json", "data": artifacts["score_pack"]},
        {"filename": f"{base}_issues.json", "mimeType": "application/json", "data": artifacts["issues_pack"]},
        {"filename": f"{base}_test_report.json", "mimeType": "application/json", "data": artifacts["test_report"]},
    ]

    files.extend(
        [
            {"filename": "summary.json", "mimeType": "application/json", "data": artifacts["legacy_summary"]},
            {
                "filename": "headings.json",
                "mimeType": "application/json",
                "data": {
                    "title": artifacts["legacy_basic"]["title"],
                    "h1": artifacts["legacy_basic"]["h1"],
                    "h2": artifacts["legacy_basic"]["h2"],
                },
            },
            {
                "filename": "meta.json",
                "mimeType": "application/json",
                "data": {
                    "description": artifacts["legacy_basic"]["description"],
                    "descriptionLength": artifacts["legacy_basic"]["descriptionLength"],
                },
            },
            {"filename": "links.json", "mimeType": "application/json", "data": artifacts["legacy_links"]},
        ]
    )

    return files


def build_internal_link_graph(parsed_pages):
    edges = defaultdict(lambda: {"from": "", "to": "", "anchors": set(), "count": 0})

    for page in parsed_pages:
        source = page.get("url")
        for link in page.get("internal_links", []):
            target = link.get("url")
            if not source or not target:
                continue
            key = (source, target)
            edge = edges[key]
            edge["from"] = source
            edge["to"] = target
            if link.get("anchor"):
                edge["anchors"].add(link.get("anchor"))
            edge["count"] += 1

    output = []
    for edge in edges.values():
        output.append(
            {
                "from": edge["from"],
                "to": edge["to"],
                "anchorTexts": sorted(list(edge["anchors"]))[:10],
                "count": edge["count"],
            }
        )

    output.sort(key=lambda item: (-item["count"], item["from"], item["to"]))
    return output


def build_summary_text(parsed_page, score_pack):
    title_ok = "presente" if parsed_page.get("title") else "ausente"
    description_ok = "presente" if parsed_page.get("meta_description") else "ausente"
    h2_count = len(parsed_page.get("headings", {}).get("h2", []))
    return (
        f"Analise concluida para {parsed_page.get('url')}. "
        f"Titulo {title_ok}, meta description {description_ok}, {h2_count} H2 encontrados. "
        f"Score AEO/GEO: {score_pack.get('total', 0)}."
    )
