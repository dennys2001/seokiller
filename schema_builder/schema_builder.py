# schema_builder.py
import json
from slugify import slugify

def build_schema(aeo):
    """
    Espera um aeo dict com chave 'markdown' contendo:
    - Conteúdo reescrito
    - FAQs
    - Definição
    - Entidades (tabela)
    Tenta extrair FAQ se existir no markdown.
    """
    md = aeo.get("markdown", "")
    title_line = md.split("\n")[0].replace("# ", "") if md else "Documento"
    # extrai FAQ simples
    faqs = []
    lines = md.splitlines()
    for i, ln in enumerate(lines):
        if ln.strip().lower().startswith("q:") or ln.strip().endswith("?"):
            q = ln.strip()
            a = lines[i+1].strip() if i+1 < len(lines) else ""
            faqs.append({"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}})
            if len(faqs) >= 5:
                break

    schema = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": title_line,
        "text": md[:1500],
        "author": {"@type": "Organization", "name": "GEO/AEO Bot"},
        "mainEntity": faqs
    }
    return json.dumps(schema, ensure_ascii=False, indent=2)
