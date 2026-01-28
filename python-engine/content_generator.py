import os
import backoff
from openai import AzureOpenAI


def resolve_openai_config(openai_cfg: dict | None):
    cfg = openai_cfg or {}
    endpoint = cfg.get("endpoint") or os.getenv("AZURE_OPENAI_ENDPOINT")
    api_key = cfg.get("apiKey") or os.getenv("AZURE_OPENAI_API_KEY")
    deployment = cfg.get("deployment") or os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini")
    if not endpoint or not api_key:
        raise RuntimeError("Azure OpenAI env vars missing (AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY)")
    return endpoint, api_key, deployment


def _get_client(openai_cfg: dict | None = None):
    endpoint, api_key, _ = resolve_openai_config(openai_cfg)
    return AzureOpenAI(
        api_version="2024-12-01-preview",
        azure_endpoint=endpoint,
        api_key=api_key,
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
def generate_aeo_content(page: dict, openai_cfg: dict | None = None, model: str | None = None, temperature: float = 0.2):
    endpoint, api_key, deployment = resolve_openai_config(openai_cfg)
    client = AzureOpenAI(
        api_version="2024-12-01-preview",
        azure_endpoint=endpoint,
        api_key=api_key,
    )
    prompt = BASE_PROMPT.format(
        title=page.get("title", ""),
        h1=page.get("h1", ""),
        text=(page.get("text", "") or "")[:15000],
        url=page.get("url", ""),
    )
    resp = client.chat.completions.create(
        model=model or deployment,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        max_tokens=2000,
    )
    content = resp.choices[0].message.content
    return {"markdown": f"# {page.get('title', '') or 'Documento'}\n\n{content}"}
