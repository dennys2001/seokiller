import re


QUESTION_PREFIXES = ("como", "quanto", "quais", "onde", "quando", "qual", "quem")


def _word_count(text: str):
    return len([token for token in re.split(r"\s+", text.strip()) if token])


def run_test_harness(primary_question, content_pack, entities, schema):
    markdown = content_pack.get("markdown", "")
    faq = content_pack.get("faq", [])
    direct_answer = content_pack.get("direct_answer", "")
    lines = markdown.splitlines()

    checks = []

    first_window = " ".join(markdown.split()[:60]).lower()
    question_tokens = {token.lower() for token in re.findall(r"[A-Za-z]{4,}", primary_question or "")}
    overlap = len([token for token in question_tokens if token in first_window])
    checks.append(
        {
            "name": "answer_in_first_60_words",
            "passed": bool(direct_answer) and overlap >= 1,
            "details": f"token_overlap={overlap}",
        }
    )

    question_headings = [line[4:].strip() for line in lines if line.startswith("### ")]
    headings_ok = bool(question_headings) and all(h.lower().startswith(QUESTION_PREFIXES) for h in question_headings)
    checks.append(
        {
            "name": "question_headings",
            "passed": headings_ok,
            "details": f"headings={len(question_headings)}",
        }
    )

    paragraphs = [
        block
        for block in markdown.split("\n\n")
        if block
        and not block.startswith("#")
        and not block.startswith("###")
        and not block.startswith("|")
        and not block.startswith("- ")
    ]
    avg_paragraph_size = int(sum(_word_count(block) for block in paragraphs) / max(1, len(paragraphs)))
    checks.append(
        {
            "name": "avg_paragraph_size",
            "passed": avg_paragraph_size <= 75,
            "details": f"avg_words={avg_paragraph_size}",
        }
    )

    faq_ok = 5 <= len(faq) <= 8
    checks.append(
        {
            "name": "faq_count_5_to_8",
            "passed": faq_ok,
            "details": f"faq_count={len(faq)}",
        }
    )

    entity_names = [entity.get("entity_name", "") for entity in entities]
    names_in_text = sum(1 for name in entity_names if name and name.lower() in markdown.lower())
    checks.append(
        {
            "name": "entities_present_in_text",
            "passed": names_in_text >= min(3, len(entity_names)),
            "details": f"entities_in_text={names_in_text}/{len(entity_names)}",
        }
    )

    faq_nodes = [node for node in schema.get("@graph", []) if node.get("@type") == "FAQPage"]
    parity_ok = True
    if faq and faq_nodes:
        schema_entities = faq_nodes[0].get("mainEntity", [])
        if len(schema_entities) != len(faq):
            parity_ok = False
        else:
            for index, qa in enumerate(faq):
                item = schema_entities[index]
                if item.get("name") != qa.get("question"):
                    parity_ok = False
                    break
                if ((item.get("acceptedAnswer") or {}).get("text") or "") != qa.get("answer"):
                    parity_ok = False
                    break
    elif faq and not faq_nodes:
        parity_ok = False

    checks.append(
        {
            "name": "schema_faq_parity",
            "passed": parity_ok,
            "details": f"faq_schema_nodes={len(faq_nodes)}",
        }
    )

    passed_checks = sum(1 for check in checks if check["passed"])
    return {"passed_checks": passed_checks, "total_checks": len(checks), "checks": checks}
