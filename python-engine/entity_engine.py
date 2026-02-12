import re
from collections import defaultdict


ENTITY_DICTIONARY = {
    "stellantis": {"type": "Organization", "aliases": ["Stellantis", "Grupo Stellantis"]},
    "chevrolet": {"type": "Brand", "aliases": ["Chevrolet"]},
    "peugeot": {"type": "Brand", "aliases": ["Peugeot"]},
    "skinceuticals": {"type": "Brand", "aliases": ["SkinCeuticals"]},
    "iof": {"type": "Tax/Regulation", "aliases": ["IOF", "Imposto sobre Operacoes Financeiras"]},
    "ipva": {"type": "Tax/Regulation", "aliases": ["IPVA"]},
    "financiamento": {"type": "FinancialProduct", "aliases": ["Financiamento"]},
    "consorcio": {"type": "FinancialProduct", "aliases": ["Consorcio"]},
    "seguro": {"type": "FinancialProduct", "aliases": ["Seguro"]},
}

MODEL_PATTERN = re.compile(r"\b(208|2008|boxer|partner(?:\s+rapid)?|sonic|onix|tracker|spin|s10)\b", re.I)
LOCATION_PATTERN = re.compile(r"\b(sao paulo|rio de janeiro|belo horizonte|curitiba|porto alegre|brasil)\b", re.I)
ORG_SUFFIX_PATTERN = re.compile(r"\b(s\.a\.|sa|ltda|inc|corp|group)\b", re.I)


def _collect_evidence(text: str, token: str, window: int = 90):
    match = re.search(re.escape(token), text, flags=re.I)
    if not match:
        return None
    start = max(0, match.start() - window)
    end = min(len(text), match.end() + window)
    return {
        "snippet": text[start:end].strip(),
        "start": match.start(),
        "end": match.end(),
    }


def extract_entities(parsed_page):
    full_text = parsed_page.get("full_text") or ""
    lowered = full_text.lower()

    entities = []
    added = set()

    for key, cfg in ENTITY_DICTIONARY.items():
        if key not in lowered:
            continue
        evidence = _collect_evidence(full_text, key)
        if not evidence:
            continue
        entity_name = cfg["aliases"][0]
        entities.append(
            {
                "entity_name": entity_name,
                "entity_type": cfg["type"],
                "aliases": cfg["aliases"],
                "evidence": evidence,
            }
        )
        added.add((entity_name.lower(), cfg["type"]))

    for match in MODEL_PATTERN.finditer(full_text):
        model = match.group(1)
        name = model.upper() if model.isnumeric() else model.title()
        key = (name.lower(), "Model")
        if key in added:
            continue
        evidence = _collect_evidence(full_text, model)
        if not evidence:
            continue
        entities.append(
            {
                "entity_name": name,
                "entity_type": "Model",
                "aliases": [name],
                "evidence": evidence,
            }
        )
        added.add(key)

    for match in LOCATION_PATTERN.finditer(lowered):
        location = match.group(1).title()
        key = (location.lower(), "Location")
        if key in added:
            continue
        evidence = _collect_evidence(full_text, match.group(1))
        if not evidence:
            continue
        entities.append(
            {
                "entity_name": location,
                "entity_type": "Location",
                "aliases": [location],
                "evidence": evidence,
            }
        )
        added.add(key)

    candidate_orgs = re.findall(r"\b([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+){0,2})\b", full_text)
    for candidate in candidate_orgs[:40]:
        if not ORG_SUFFIX_PATTERN.search(candidate):
            continue
        key = (candidate.lower(), "Organization")
        if key in added:
            continue
        evidence = _collect_evidence(full_text, candidate)
        if not evidence:
            continue
        entities.append(
            {
                "entity_name": candidate,
                "entity_type": "Organization",
                "aliases": [candidate],
                "evidence": evidence,
            }
        )
        added.add(key)

    entities.sort(key=lambda item: (item["entity_type"], item["entity_name"]))
    return entities


def aggregate_sitewide_entities(pages_entities):
    merged = defaultdict(
        lambda: {
            "entity_name": "",
            "entity_type": "",
            "aliases": set(),
            "mentions": 0,
            "evidence": [],
        }
    )

    for page_item in pages_entities:
        page_url = page_item.get("url")
        for entity in page_item.get("entities", []):
            key = (entity.get("entity_name", "").lower(), entity.get("entity_type", ""))
            record = merged[key]
            record["entity_name"] = entity.get("entity_name", "")
            record["entity_type"] = entity.get("entity_type", "")
            for alias in entity.get("aliases", []):
                record["aliases"].add(alias)
            record["mentions"] += 1

            evidence = dict(entity.get("evidence", {}))
            if page_url:
                evidence["url"] = page_url
            record["evidence"].append(evidence)

    output = []
    for record in merged.values():
        output.append(
            {
                "entity_name": record["entity_name"],
                "entity_type": record["entity_type"],
                "aliases": sorted(record["aliases"]),
                "mentions": record["mentions"],
                "evidence": record["evidence"][:5],
            }
        )
    output.sort(key=lambda item: (-item["mentions"], item["entity_name"]))
    return output
