import re
from urllib.parse import urlparse


QUESTION_BANK = {
    "informacional_comparativa": [
        "Quais sao os principais diferenciais deste modelo?",
        "Quais versoes estao disponiveis e o que muda entre elas?",
        "Qual e a faixa de preco e quais itens estao incluidos?",
        "Como este modelo se compara com alternativas da mesma categoria?",
        "Quais custos de manutencao e garantia sao informados?",
        "Onde consultar especificacoes tecnicas completas?",
    ],
    "transacional": [
        "Qual e a oferta ativa e para quem ela se aplica?",
        "Quais sao as condicoes de entrada, parcelas e taxas?",
        "Quais documentos sao necessarios para contratacao?",
        "Ha regras de elegibilidade ou restricoes por perfil?",
        "Como simular e concluir a contratacao passo a passo?",
        "Onde validar prazo de vigencia da oferta?",
    ],
    "local": [
        "Onde ficam as unidades de atendimento?",
        "Quais sao os horarios de funcionamento por regiao?",
        "Como agendar visita, test-drive ou atendimento?",
        "Quais contatos oficiais estao disponiveis?",
        "Ha servicos especificos por unidade?",
        "Como confirmar cobertura na minha cidade?",
    ],
    "navegacional": [
        "Qual secao resolve mais rapido a necessidade principal?",
        "Onde encontrar contato e canais oficiais?",
        "Como navegar para paginas de produto, oferta e suporte?",
        "Quais links internos sao prioritarios?",
        "Onde estao politicas e informacoes legais?",
    ],
}


def detect_intent(url: str, parsed_page):
    path = urlparse(url).path.lower()
    title = (parsed_page.get("title") or "").lower()
    full_text = (parsed_page.get("full_text") or "").lower()
    corpus = " ".join([path, title, full_text])

    # Title is a strong hint. Some "gama/modelos" pages include pricing modules,
    # but the primary intent is still informational/comparative.
    if any(key in title for key in ("modelos", "gama", "our range", "our-range", "linha")):
        return "informacional_comparativa"

    if any(key in path for key in ("/ofertas", "/comprar", "/financiamento", "/buy", "/oferta")):
        return "transacional"
    if any(key in path for key in ("/modelos", "/gama", "/our-range")):
        return "informacional_comparativa"
    if any(key in path for key in ("/concessionarias", "/dealers", "/lojas", "/store-locator")):
        return "local"

    if "compar" in corpus or "diferen" in corpus:
        return "informacional_comparativa"
    if any(key in corpus for key in ("agendar", "compre", "simule", "oferta", "financiamento")):
        return "transacional"
    if any(key in corpus for key in ("endereco", "unidade", "concessionaria", "bairro", "cidade")):
        return "local"
    return "navegacional"


def infer_primary_question(intent: str, parsed_page):
    title = parsed_page.get("title") or "esta pagina"
    if intent == "transacional":
        return f"Quais condicoes desta oferta em {title} e como contratar?"
    if intent == "local":
        return f"Onde encontrar atendimento e como agendar em {title}?"
    if intent == "informacional_comparativa":
        return f"Quais sao as versoes, diferencas e dados principais de {title}?"
    return f"Qual e a informacao principal disponivel em {title}?"


def infer_secondary_questions(intent: str, parsed_page, limit: int = 6):
    questions = list(QUESTION_BANK.get(intent, QUESTION_BANK["navegacional"]))
    h2_text = " ".join(parsed_page.get("headings", {}).get("h2", []))
    full_text = parsed_page.get("full_text", "")

    if re.search(r"\bgarantia\b", h2_text, flags=re.I):
        questions.insert(0, "Qual garantia oficial e informada para este item?")
    if re.search(r"\bconsumo|km/l|autonomia\b", full_text, flags=re.I):
        questions.insert(0, "Quais numeros de consumo e autonomia foram publicados?")

    cleaned = []
    seen = set()
    for question in questions:
        normalized = question.strip()
        if normalized.lower().startswith("o que e "):
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        cleaned.append(normalized)
    return cleaned[: max(3, min(limit, 8))]
