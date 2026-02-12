import re


QUESTION_PREFIXES = ("Como", "Quanto", "Quais", "Onde", "Quando", "Qual", "Quem")


def _first_sentence(text: str):
    if not text:
        return ""
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return (parts[0] or "").strip()


def _truncate_words(text: str, max_words: int = 60) -> str:
    words = (text or "").split()
    if len(words) <= max_words:
        return text or ""
    return " ".join(words[:max_words]).rstrip(",.;:") + "..."


def _extract_facts(parsed_page):
    text = parsed_page.get("full_text", "")
    facts = {
        "price": None,
        "versions": None,
        "consumption": None,
        "warranty": None,
        "address_or_contact": None,
    }

    price_match = re.search(r"(r\$\s?\d[\d\.,]*)", text, flags=re.I)
    if price_match:
        facts["price"] = price_match.group(1)

    version_match = re.search(r"(vers(?:ao|oes|oes).{0,100})", text, flags=re.I)
    if version_match:
        facts["versions"] = version_match.group(1).strip()

    consumo_match = re.search(r"(\d{1,2}\s?km\/l|consumo.{0,80})", text, flags=re.I)
    if consumo_match:
        facts["consumption"] = consumo_match.group(1).strip()

    garantia_match = re.search(r"(garantia.{0,100})", text, flags=re.I)
    if garantia_match:
        facts["warranty"] = garantia_match.group(1).strip()

    contact_match = re.search(r"(telefone.{0,80}|whatsapp.{0,80}|endereco.{0,120})", text, flags=re.I)
    if contact_match:
        facts["address_or_contact"] = contact_match.group(1).strip()

    return facts


def _build_faq(questions, facts):
    faq = []
    for question in questions[:8]:
        q = question.strip()
        if q.lower().startswith("o que e "):
            continue

        ql = q.lower()
        if "preco" in ql:
            answer = f"O preco informado na fonte e {facts['price']}." if facts.get("price") else "Preco nao informado na fonte."
        elif "vers" in ql:
            answer = facts.get("versions") or "Versoes nao informadas na fonte."
        elif "consumo" in ql or "autonomia" in ql:
            answer = facts.get("consumption") or "Consumo nao informado na fonte."
        elif "garantia" in ql:
            answer = facts.get("warranty") or "Garantia nao informada na fonte."
        elif "onde" in ql or "contato" in ql or "agendar" in ql:
            answer = facts.get("address_or_contact") or "Contato e endereco nao informados na fonte."
        elif "taxa" in ql or "entrada" in ql or "parcela" in ql:
            answer = "Condicoes financeiras devem ser confirmadas na pagina fonte."
        else:
            answer = "Informacao nao identificada com precisao na fonte. Recomenda-se publicar este dado explicitamente."

        faq.append({"question": q, "answer": answer})

    return faq[:8]


def _normalize_question_heading(question: str):
    if any(question.startswith(prefix) for prefix in QUESTION_PREFIXES):
        return question
    return f"Como {question[0].lower()}{question[1:]}"


def _write_intent_sections(lines, intent, parsed_page, facts):
    paragraphs = parsed_page.get("paragraphs", [])
    internal_links = parsed_page.get("internal_links", [])

    if intent == "informacional_comparativa":
        lines.append("## O que voce encontra nesta pagina")
        if paragraphs:
            lines.append(_truncate_words(paragraphs[0], 60))
        else:
            lines.append("A fonte nao traz uma descricao editorial clara; esta pagina parece funcionar como indice/navegacao para modelos e servicos.")
        lines.append("")

        model_links = []
        for link in internal_links:
            href = (link.get("url") or "").lower()
            anchor = (link.get("anchor") or "").strip()
            if not anchor:
                continue
            if any(key in href for key in ("/gama/", "/modelos/", "/our-range/", "/our-range/")):
                model_links.append((anchor, link.get("url")))
        dedup = []
        seen = set()
        for a, u in model_links:
            if u in seen:
                continue
            seen.add(u)
            dedup.append((a, u))
        if dedup:
            lines.append("## Principais links de modelos/linha")
            for a, u in dedup[:8]:
                lines.append(f"- {a}: {u}")
            lines.append("")

        lines.append("## Versoes e principais diferencas")
        lines.append(f"- {facts['versions']}" if facts.get("versions") else "- Versoes nao informadas na fonte.")
        lines.append("")

        lines.append("## Preco")
        lines.append(f"- Valor identificado: {facts['price']}" if facts.get("price") else "- Preco nao informado na fonte.")
        lines.append("")

    elif intent == "transacional":
        lines.append("## Qual e a oferta e para quem serve")
        lines.append(paragraphs[0] if paragraphs else "A oferta nao esta detalhada na fonte.")
        lines.append("")

        lines.append("## Condicoes")
        if facts.get("price"):
            lines.append(f"- Preco ou valor citado: {facts['price']}")
        else:
            lines.append("- Entrada, parcelas e taxas nao informadas na fonte.")
        lines.append("")

        lines.append("## Como aproveitar a oferta")
        lines.append("1. Consulte a pagina oficial da oferta.")
        lines.append("2. Valide elegibilidade e documentos.")
        lines.append("3. Confirme prazo de vigencia e condicoes finais.")
        lines.append("")

    elif intent == "local":
        lines.append("## Onde encontrar atendimento")
        lines.append(facts.get("address_or_contact") or "Endereco e contato nao informados na fonte.")
        lines.append("")

        lines.append("## Como agendar")
        lines.append("- Verifique se a pagina disponibiliza formulario, telefone ou canal oficial.")
        lines.append("- Se nao houver canal explicito, publicar instrucao de agendamento e recomendado.")
        lines.append("")

    else:
        lines.append("## Informacoes principais")
        if paragraphs:
            for paragraph in paragraphs[:3]:
                lines.append(f"- {paragraph}")
        else:
            lines.append("- A fonte nao trouxe contexto suficiente.")
        lines.append("")


def generate_aeo_markdown(parsed_page, intent, primary_question, secondary_questions, entities, expected_gaps):
    title = parsed_page.get("title") or "Pagina sem titulo"
    paragraphs = parsed_page.get("paragraphs", [])

    facts = _extract_facts(parsed_page)
    if intent == "informacional_comparativa":
        direct_answer = (
            "Esta pagina funciona como indice para a gama de modelos e paginas relacionadas (modelos, ofertas e servicos). "
            "Para dados como preco, versoes e especificacoes, consulte a pagina especifica de cada modelo."
        )
    elif intent == "local":
        direct_answer = _first_sentence(parsed_page.get("meta_description", "")) or "Esta pagina direciona para unidades/canais de atendimento; detalhes completos nao foram identificados na fonte."
    else:
        direct_answer = _first_sentence(paragraphs[0] if paragraphs else parsed_page.get("meta_description", ""))
        if not direct_answer:
            direct_answer = "A fonte nao publica resposta direta suficiente para a pergunta principal."
    if len(direct_answer.split()) > 35:
        direct_answer = " ".join(direct_answer.split()[:35]).rstrip(",.;:") + "."

    faq = _build_faq(secondary_questions, facts)

    lines = [f"# {title}", "", f"**Resposta direta:** {direct_answer}", ""]
    lines.append(f"## {primary_question}")
    if intent == "informacional_comparativa":
        lines.append(
            "A fonte nao consolida uma explicacao unica em texto corrido; trate esta pagina como um indice. "
            "Use os links internos para abrir o modelo/tema especifico e entao coletar dados (preco, versoes, consumo, garantia) da pagina correta."
        )
    else:
        lines.append(paragraphs[0] if paragraphs else "A fonte nao trouxe um bloco explicativo completo para esta pergunta.")
    lines.append("")

    _write_intent_sections(lines, intent, parsed_page, facts)

    lines.append("## Entidades relevantes")
    lines.append("| Entidade | Tipo |")
    lines.append("| --- | --- |")
    if entities:
        for entity in entities[:10]:
            lines.append(f"| {entity.get('entity_name')} | {entity.get('entity_type')} |")
    else:
        lines.append("| Nao informado | Nao informado |")
    lines.append("")

    lines.append("## Perguntas frequentes")
    for qa in faq:
        lines.append(f"### {_normalize_question_heading(qa['question'])}")
        lines.append(qa["answer"])
        lines.append("")

    lines.append("## Dados nao informados")
    if expected_gaps:
        for gap in expected_gaps:
            lines.append(f"- {gap['message']}. Recomenda-se publicar este dado de forma explicita.")
    else:
        lines.append("- A fonte cobre os dados esperados para esta intencao.")

    return {
        "markdown": "\n".join(lines).strip(),
        "direct_answer": direct_answer,
        "faq": faq,
        "facts": facts,
    }
