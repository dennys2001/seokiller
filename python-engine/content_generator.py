import re


def _clean_text(text: str) -> str:
    return " ".join((text or "").split())


def _sentences(text: str):
    if not text:
        return []
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if p.strip()]


def _extract_keywords(text: str, limit: int = 8):
    words = re.findall(r"\b[a-zA-ZÀ-ÿ0-9-]{3,}\b", text.lower())
    stop = {
        "para", "como", "com", "sem", "dos", "das", "que", "uma", "um", "uns", "umas",
        "por", "mais", "menos", "sua", "seu", "são", "ser", "sendo", "foi", "isso",
        "essa", "este", "esta", "porque", "quando", "onde", "sobre", "entre", "muito",
        "tem", "têm", "com", "não", "sim", "nos", "nas", "aos", "às", "ao", "na", "no",
    }
    freq = {}
    for w in words:
        if w in stop:
            continue
        freq[w] = freq.get(w, 0) + 1
    ranked = sorted(freq.items(), key=lambda x: (-x[1], x[0]))
    return [k for k, _ in ranked[:limit]]


def _make_faqs(title: str, keywords: list[str]):
    faqs = []
    if title:
        faqs.append((f"O que é {title}?", "É uma página com informações resumidas e pontos-chave sobre o tema."))
    if keywords:
        faqs.append((f"Quais são os tópicos principais?", "Eles incluem: " + ", ".join(keywords[:6]) + "."))
    faqs.append(("Como usar este conteúdo?", "Leia os tópicos principais e use as respostas como guia prático."))
    faqs.append(("Para quem este conteúdo é útil?", "Para pessoas buscando uma visão rápida e objetiva sobre o tema."))
    faqs.append(("Onde posso saber mais?", "Explore o site e as fontes citadas para aprofundar o assunto."))
    return faqs[:5]


def generate_aeo_content(page: dict):
    title = _clean_text(page.get("title", "")) or "Documento"
    h1 = _clean_text(page.get("h1", ""))
    text = _clean_text(page.get("text", ""))
    sentences = _sentences(text)
    summary = " ".join(sentences[:4]) or "Resumo indisponível para esta página."
    definition = sentences[0] if sentences else "Definição indisponível para esta página."
    keywords = _extract_keywords(text)
    faqs = _make_faqs(title, keywords)

    lines = []
    lines.append(summary)
    lines.append("")
    lines.append("## Perguntas Frequentes")
    for q, a in faqs:
        lines.append(f"**{q}**")
        lines.append(a)
        lines.append("")
    lines.append("## Definição")
    lines.append(definition)
    lines.append("")
    lines.append("## Entidades Principais")
    if keywords:
        lines.append("| Entidade | Categoria |")
        lines.append("| --- | --- |")
        for k in keywords:
            lines.append(f"| {k.title()} | Termo |")
    else:
        lines.append("Sem entidades detectadas.")

    content = "\n".join(lines).strip()
    return {"markdown": f"# {title}\n\n{content}"}
