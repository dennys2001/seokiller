import re


QUESTION_PREFIXES = ("como", "quanto", "quais", "onde", "quando", "qual", "quem")


def _paragraphs_from_markdown(markdown: str):
    blocks = [block.strip() for block in markdown.split("\n\n") if block.strip()]
    paragraphs = []
    for block in blocks:
        if block.startswith("#") or block.startswith("|") or block.startswith("- ") or block.startswith("###"):
            continue
        paragraphs.append(block)
    return paragraphs


def compute_aeo_score(intent, primary_question, entities, content_pack, schema, secondary_questions):
    markdown = content_pack.get("markdown", "")
    lines = markdown.splitlines()
    direct_answer = content_pack.get("direct_answer", "")
    faq = content_pack.get("faq", [])
    paragraphs = _paragraphs_from_markdown(markdown)

    breakdown = {
        "answer_first": {"score": 0, "max": 20, "rules_failed": []},
        "extractability": {"score": 0, "max": 20, "rules_failed": []},
        "entity_clarity": {"score": 0, "max": 20, "rules_failed": []},
        "coverage": {"score": 0, "max": 20, "rules_failed": []},
        "schema_parity": {"score": 0, "max": 20, "rules_failed": []},
    }

    sentence_count = len([chunk for chunk in re.split(r"[.!?]+", direct_answer) if chunk.strip()])
    if direct_answer and 1 <= sentence_count <= 2:
        breakdown["answer_first"]["score"] += 12
    else:
        breakdown["answer_first"]["rules_failed"].append("Resposta direta ausente ou fora de 1-2 frases")

    if any(line.strip().lower().startswith("**resposta direta:**") for line in lines[:6]):
        breakdown["answer_first"]["score"] += 8
    else:
        breakdown["answer_first"]["rules_failed"].append("Resposta direta nao esta no topo")

    heading_lines = re.findall(r"^###\s+(.+)$", markdown, flags=re.M)
    if heading_lines:
        prefix_hits = sum(1 for heading in heading_lines if heading.strip().lower().startswith(QUESTION_PREFIXES))
        breakdown["extractability"]["score"] += min(10, prefix_hits * 2)
        if prefix_hits < len(heading_lines):
            breakdown["extractability"]["rules_failed"].append("Nem todos os headings estao em formato de pergunta")
    else:
        breakdown["extractability"]["rules_failed"].append("Faltam headings em formato pergunta")

    if any(line.startswith("- ") for line in lines):
        breakdown["extractability"]["score"] += 5
    else:
        breakdown["extractability"]["rules_failed"].append("Faltam listas curtas")

    if "|" in markdown:
        breakdown["extractability"]["score"] += 5
    else:
        breakdown["extractability"]["rules_failed"].append("Falta tabela simples de entidades")

    valid_entities = [entity for entity in entities if entity.get("evidence", {}).get("snippet")]
    entity_types = {entity.get("entity_type") for entity in valid_entities}
    breakdown["entity_clarity"]["score"] += min(12, len(valid_entities))
    breakdown["entity_clarity"]["score"] += min(8, len(entity_types) * 2)
    if len(valid_entities) < 4:
        breakdown["entity_clarity"]["rules_failed"].append("Poucas entidades com evidencia")
    if len(entity_types) < 2:
        breakdown["entity_clarity"]["rules_failed"].append("Baixa diversidade de tipos de entidade")

    covered = 0
    markdown_lower = markdown.lower()
    for question in secondary_questions:
        first_token = question.split()[0].lower()
        if first_token in markdown_lower:
            covered += 1
    ratio = covered / max(1, len(secondary_questions))
    breakdown["coverage"]["score"] = min(20, int(round(ratio * 20)))
    if ratio < 0.6:
        breakdown["coverage"]["rules_failed"].append("Cobertura baixa das intencoes secundarias")

    faq_nodes = [node for node in schema.get("@graph", []) if node.get("@type") == "FAQPage"]
    if faq and faq_nodes:
        breakdown["schema_parity"]["score"] += 10
    elif faq and not faq_nodes:
        breakdown["schema_parity"]["rules_failed"].append("FAQPage ausente")
    else:
        breakdown["schema_parity"]["score"] += 6

    if schema.get("@graph"):
        breakdown["schema_parity"]["score"] += 5
    else:
        breakdown["schema_parity"]["rules_failed"].append("Schema vazio")

    mismatch = False
    if faq_nodes and faq:
        main_entities = faq_nodes[0].get("mainEntity", [])
        if len(main_entities) != len(faq):
            mismatch = True
        else:
            for index, qa in enumerate(faq):
                schema_item = main_entities[index]
                if schema_item.get("name") != qa.get("question"):
                    mismatch = True
                    break
                schema_answer = ((schema_item.get("acceptedAnswer") or {}).get("text") or "")
                if schema_answer != qa.get("answer"):
                    mismatch = True
                    break

    if mismatch:
        breakdown["schema_parity"]["rules_failed"].append("Paridade schema-conteudo quebrada")
    else:
        breakdown["schema_parity"]["score"] += 5

    total = sum(item["score"] for item in breakdown.values())
    return {
        "total": max(0, min(100, total)),
        "breakdown": breakdown,
        "intent": intent,
        "primary_question": primary_question,
        "paragraph_count": len(paragraphs),
    }
