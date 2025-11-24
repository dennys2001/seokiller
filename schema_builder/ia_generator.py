# ia_generator.py
import os
from dotenv import load_dotenv
load_dotenv()
from openai import AzureOpenAI
import time
import backoff

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY not set in environment")

#client = OpenAI(api_key=OPENAI_API_KEY)

client = AzureOpenAI(
    api_version="2024-12-01-preview",
    azure_endpoint="https://ai-teste258202003763.cognitiveservices.azure.com/",
    api_key=OPENAI_API_KEY
)

BASE_PROMPT_TEMPLATE = """
Você é um especialista em AEO (Answer Engine Optimization) e GEO (Generative Engine Optimization).
Com base no conteúdo a seguir, gere EXATAMENTE os entregáveis indicados e na ordem solicitada.

Conteúdo a ser otimizado:
Título: {title}
H1: {h1}
Texto: {text}
URL: {url}

Entregáveis:
1) Conteúdo reescrito (AEO+GEO) — scannable, parágrafos curtos.
2) 5 FAQs (respostas <= 50 palavras).
3) Definição estilo Wikipédia (1 parágrafo).
4) Entidades principais em tabela (Entidade | Categoria).

Saída: Retorne em MARKDOWN somente os itens na ordem solicitada, sem comentários extras.
"""

@backoff.on_exception(backoff.expo, Exception, max_tries=5, jitter=backoff.full_jitter)
def generate_aeo_content(page, model="gpt-4", temperature=0.2):
    prompt = BASE_PROMPT_TEMPLATE.format(
        title=page.get("title", ""),
        h1=page.get("h1", ""),
        text=page.get("text", "")[:15000],  # limita para não estourar token
        url=page.get("url", "")
    )

    # Use chat completions via new OpenAI client
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        max_tokens=2000
    )
    content = resp.choices[0].message.content
    # retorna markdown como no projeto original
    return {"markdown": f"# {page.get('title', '')}\n\n{content}"}
