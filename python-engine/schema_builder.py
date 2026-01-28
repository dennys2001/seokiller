import json
import re


def extract_faqs_from_markdown(md: str):
    faqs = []
    lines = md.splitlines()
    for i, line in enumerate(lines):
        question = line.strip()
        if not question:
            continue
        if question.lower().startswith("q:") or question.endswith("?"):
            answer = lines[i + 1].strip() if i + 1 < len(lines) else ""
            faqs.append(
                {
                    "@type": "Question",
                    "name": question,
                    "acceptedAnswer": {"@type": "Answer", "text": answer},
                }
            )
        if len(faqs) >= 5:
            break
    return faqs


def build_schema(aeo: dict, page: dict | None = None):
    md = aeo.get("markdown", "") if aeo else ""
    title_line = md.split("\n")[0].replace("# ", "") if md else "Documento"
    faqs = extract_faqs_from_markdown(md)
    text = md[:1500]
    schema = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": title_line,
        "text": text,
        "author": {"@type": "Organization", "name": "GEO/AEO Bot"},
    }
    if faqs:
        schema["mainEntity"] = faqs
        schema["@type"] = ["Article", "FAQPage"]
    if page and page.get("url"):
        schema["url"] = page["url"]
    # basic GEO hint: extract locale from url path (very rough)
    if page and page.get("url"):
        m = re.search(r"/([a-z]{2}-[A-Z]{2})/", page["url"])
        if m:
            schema["inLanguage"] = m.group(1)
    return json.dumps(schema, ensure_ascii=False, indent=2)
