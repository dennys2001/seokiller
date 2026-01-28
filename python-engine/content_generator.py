import os
import backoff
from openai import AzureOpenAI


AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini")


def _get_client():
    if not AZURE_OPENAI_API_KEY or not AZURE_OPENAI_ENDPOINT:
        raise RuntimeError("Azure OpenAI env vars missing (AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY)")
    return AzureOpenAI(
        api_version="2024-12-01-preview",
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_API_KEY,
    )


BASE_PROMPT = """You are an expert in AEO (Answer Engine Optimization) and GEO (Generative Engine Optimization).
Rewrite the content to be scannable, concise, and ready for AI answer engines. Then produce the deliverables below.

Input:
Title: {title}
H1: {h1}
Text: {text}
URL: {url}

Deliverables (in Portuguese):
1) Conteudo reescrito (paragrafos curtos, foco em resposta direta).
2) 5 FAQs com respostas (<= 50 palavras cada).
3) Definicao estilo Wikipedia (1 paragrafo).
4) Tabela de entidades principais (Entidade | Categoria).

Output: Return ONLY the deliverables above in Markdown, in that order, without extra commentary.
"""


@backoff.on_exception(backoff.expo, Exception, max_tries=5, jitter=backoff.full_jitter)
def generate_aeo_content(page: dict, model: str | None = None, temperature: float = 0.2):
    client = _get_client()
    prompt = BASE_PROMPT.format(
        title=page.get("title", ""),
        h1=page.get("h1", ""),
        text=(page.get("text", "") or "")[:15000],
        url=page.get("url", ""),
    )
    resp = client.chat.completions.create(
        model=model or AZURE_OPENAI_DEPLOYMENT,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        max_tokens=2000,
    )
    content = resp.choices[0].message.content
    return {"markdown": f"# {page.get('title', '') or 'Documento'}\n\n{content}"}
