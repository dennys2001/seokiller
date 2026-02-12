def build_schema_ld(parsed_page, content_pack, intent, entities):
    url = parsed_page.get("url")
    title = parsed_page.get("title") or "Pagina"
    direct_answer = content_pack.get("direct_answer") or ""
    faq = content_pack.get("faq") or []
    breadcrumbs = parsed_page.get("breadcrumbs") or []
    facts = content_pack.get("facts") or {}

    graph = [
        {
            "@type": "WebPage",
            "@id": f"{url}#webpage",
            "url": url,
            "name": title,
            "description": direct_answer,
        }
    ]

    if breadcrumbs:
        graph.append(
            {
                "@type": "BreadcrumbList",
                "@id": f"{url}#breadcrumbs",
                "itemListElement": [
                    {
                        "@type": "ListItem",
                        "position": index + 1,
                        "name": crumb.get("name"),
                        "item": crumb.get("url"),
                    }
                    for index, crumb in enumerate(breadcrumbs)
                ],
            }
        )

    organization = next((entity for entity in entities if entity.get("entity_type") == "Organization"), None)
    if organization:
        graph.append(
            {
                "@type": "Organization",
                "@id": f"{url}#organization",
                "name": organization.get("entity_name"),
            }
        )

    if faq:
        graph.append(
            {
                "@type": "FAQPage",
                "@id": f"{url}#faq",
                "mainEntity": [
                    {
                        "@type": "Question",
                        "name": qa["question"],
                        "acceptedAnswer": {
                            "@type": "Answer",
                            "text": qa["answer"],
                        },
                    }
                    for qa in faq
                ],
            }
        )

    if intent == "local" and facts.get("address_or_contact"):
        graph.append(
            {
                "@type": "AutoDealer",
                "@id": f"{url}#autodealer",
                "name": title,
                "description": facts.get("address_or_contact"),
            }
        )

    if intent == "informacional_comparativa":
        graph.append(
            {
                "@type": "HowTo",
                "@id": f"{url}#howto",
                "name": f"Como analisar {title}",
                "step": [
                    {"@type": "HowToStep", "text": "Revisar resposta direta e dados principais."},
                    {"@type": "HowToStep", "text": "Comparar versoes, preco e garantia com base na fonte."},
                ],
            }
        )

    return {"@context": "https://schema.org", "@graph": graph}


def check_schema_parity(schema, content_pack):
    faq_nodes = [node for node in schema.get("@graph", []) if node.get("@type") == "FAQPage"]
    content_faq = content_pack.get("faq") or []

    if not faq_nodes and not content_faq:
        return True, []
    if content_faq and not faq_nodes:
        return False, ["Schema FAQPage ausente apesar de FAQ existir"]

    errors = []
    schema_faq = faq_nodes[0].get("mainEntity", [])

    if len(schema_faq) != len(content_faq):
        errors.append("Quantidade de perguntas no schema difere do conteudo")

    for index, qa in enumerate(content_faq):
        if index >= len(schema_faq):
            break
        schema_item = schema_faq[index]
        if schema_item.get("name") != qa.get("question"):
            errors.append(f"Pergunta {index + 1} no schema difere do conteudo")
        answer = ((schema_item.get("acceptedAnswer") or {}).get("text") or "").strip()
        if answer != (qa.get("answer") or "").strip():
            errors.append(f"Resposta {index + 1} no schema difere do conteudo")

    return len(errors) == 0, errors
