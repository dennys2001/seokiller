# Python SEO/GEO/AEO Engine

This is a Flask-based engine that analyzes a web page for SEO, GEO (local) and AEO (answer engine) signals and returns a structured payload compatible with the existing middleware and frontend.

It mirrors the mock engine’s response shape:

- Top-level fields: `analyzedUrl`, `summary`, and optionally `optimizedContent`
- `files`: array of `{ filename, mimeType, data }`
  - `summary.json` → `{ url, score, issues: [{ type, message }] }`
  - `headings.json` → `{ title, h1: string[], h2: string[] }`
  - `meta.json` → `{ description, descriptionLength }`
  - `links.json` → `{ internal: string[], external: string[] }`

## Run locally

1) Create a virtualenv and install dependencies

```
cd seokiller/python-engine
python -m venv .venv
.\.venv\Scripts\activate  # Windows PowerShell
pip install -r requirements.txt
```

2) Start the engine

```
set ENGINE_PORT=5000
python app.py
```

3) Point the middleware to this engine

In another terminal, in `seokiller/server`, set:

```
set ENGINE_URL=http://localhost:5000/analyze
npm start
```

The frontend (`wcs`) should remain unchanged and continue to call the middleware `/avalie` endpoint.

## Notes

- Network access is required when the engine runs to fetch and analyze target URLs.
- The scoring is heuristic-based and conservative; adjust weights as needed.
- If a page blocks bots or returns a non-HTML response, the engine handles it gracefully and reports issues.
