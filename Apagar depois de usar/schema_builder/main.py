from dotenv import load_dotenv
load_dotenv()
import os
from crawler import crawl_site
from ia_generator import generate_aeo_content
from schema_builder import build_schema
import re

def main():
    url = os.getenv("SITE_URL")
    if not url:
        print("[ERRO] SITE_URL não definida no .env")
        return

    print(f"[INFO] Iniciando varredura de {url}")
    pages = crawl_site(url)
    print(f"[INFO] {len(pages)} páginas capturadas")

    for p in pages:
        print(f"[INFO] Processando: {p['url']}")
        aeo = generate_aeo_content(p)
        schema = build_schema(aeo)
        save_outputs(p['url'], aeo, schema)

import re

def save_outputs(url, aeo, schema):
    # remove protocolo e limpa caracteres inválidos
    safe = re.sub(r'[^a-zA-Z0-9\-_]', '_', url.replace("https://", "").replace("http://", ""))
    safe = safe[:100]  # limite de caracteres
    os.makedirs("geo_content", exist_ok=True)
    with open(f"geo_content/{safe}.md", "w", encoding="utf-8") as f:
        f.write(aeo["markdown"])
    with open(f"geo_content/{safe}.json", "w", encoding="utf-8") as f:
        f.write(schema)
    print(f"[SALVO] geo_content/{safe}.*")
    
if __name__ == "__main__":
    main()