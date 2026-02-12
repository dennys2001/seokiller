# Python SEO/GEO/AEO Engine

Flask engine that fetches a URL (optionally crawls a domain), parses the main content, and generates **AEO/GEO artifacts** (answer-first, extractable content + entities + schema parity + scoring + tests).

The response is compatible with the existing middleware/frontend shape:

- Top-level fields: `analyzedUrl`, `summary`, `optimizedContent`
- `files`: array of `{ filename, mimeType, data }`
- Also returns `analysisDetails` for the UI (intent, primary question, top entities, breakdown, issues, tests).

## Artifacts (per URL)

- `*_page.md`: AEO/GEO Markdown with `**Resposta direta:**` at the top, question-led sections, entity table, FAQ, and "Dados nao informados"
- `*_page.json`: page metadata (intent, primary question, direct answer, etc.)
- `*_entities.json`: extracted entities with evidence snippets and positions
- `*_schema.json`: JSON-LD graph (WebPage + optional BreadcrumbList, Organization, FAQPage, etc.) with parity against content
- `*_score.json`: AEO/GEO score (0-100) with breakdown (auditavel)
- `*_issues.json`: issues by category (Technical SEO / AEO Content Quality / Structured Data)
- `*_test_report.json`: deterministic test harness (no external LLM calls)

Legacy compatibility files are also included:

- `summary.json`, `headings.json`, `meta.json`, `links.json`

Crawler mode (`useCrawler=true`) appends:

- `entities_sitewide.json`: aggregated entities across crawled pages
- `internal_link_graph.json`: internal link edges with anchor text samples

## Run locally

1. Install deps

```powershell
cd seokiller/python-engine
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

2. Start engine

```powershell
set ENGINE_PORT=5000
python app.py
```

3. Point the middleware to this engine (in `seokiller/server`)

```powershell
set ENGINE_URL=http://localhost:5000/analyze
npm start
```

Frontend (`wcs`) keeps calling `/avalie` (middleware).

## Environment variables

- `ENGINE_PORT` (default `5000`): Flask port
- `ENGINE_REQUEST_TIMEOUT` (default `180`): fetch timeout (seconds) for direct (non-crawler) mode
- `PLAYWRIGHT_FALLBACK` (default `1`): enable Playwright fallback on bot challenge / maintenance pages
- `PLAYWRIGHT_MAX_FALLBACKS` (default `2`): max Playwright fallbacks during a crawl

## How to extend templates

Primary places to edit:

- `python-engine/intent_engine.py`: intent detection + question generation
- `python-engine/content_generator_aeo.py`: answer-first Markdown generation by intent
- `python-engine/schema_engine.py`: JSON-LD types and parity rules

Hard rule: do not invent data; if missing, mark as not informed and recommend publishing it.

## Validation

- Unit tests:

```powershell
python -m unittest discover -s python-engine/tests -p "test_*.py"
```

- Front build on Windows with PowerShell execution policy restrictions:

```powershell
npm.cmd -C wcs run build
```

## Notes

- Network access is required to fetch target URLs.
- Anti-bot / maintenance handling:
  - Direct mode: `requests` first, then Playwright (if enabled) when the HTML looks blocked/unusable.
  - Crawler mode: blocked/unusable pages are discarded; if no valid pages remain, the engine falls back to a summary response with a warning.

