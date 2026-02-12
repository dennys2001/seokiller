def build_issues(parsed_page, score_pack, content_pack, entities, schema_parity_ok, schema_parity_errors, expected_gaps):
    technical = []
    aeo_quality = []
    structured = []

    if not parsed_page.get("meta_description"):
        technical.append("Meta description ausente")
    if len(parsed_page.get("headings", {}).get("h2", [])) < 1:
        technical.append("Poucos H2")
    if not parsed_page.get("flags", {}).get("has_hreflang"):
        technical.append("hreflang ausente")

    answer_failures = score_pack.get("breakdown", {}).get("answer_first", {}).get("rules_failed", [])
    if answer_failures:
        aeo_quality.append("Resposta direta ausente ou longa demais")

    if any((qa.get("question") or "").lower().startswith("o que e ") for qa in content_pack.get("faq", [])):
        aeo_quality.append("FAQ com perguntas artificiais")

    if len(entities) < 4:
        aeo_quality.append("Entidades mal classificadas ou tokens soltos")

    if expected_gaps:
        aeo_quality.append("Dados criticos esperados ausentes na fonte")

    schema_graph = content_pack.get("schema_graph") or []
    if content_pack.get("faq") and not any(node.get("@type") == "FAQPage" for node in schema_graph):
        structured.append("Schema FAQPage ausente apesar de FAQ existir")

    if not schema_parity_ok:
        structured.append("Paridade schema<->conteudo quebrada")
        structured.extend(schema_parity_errors)

    return {
        "Technical SEO": sorted(set(technical)),
        "AEO/GEO Content Quality": sorted(set(aeo_quality)),
        "Structured Data": sorted(set(structured)),
    }
