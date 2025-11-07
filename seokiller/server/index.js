require('dotenv').config();

const express = require('express');
const cors = require('cors');
const archiver = require('archiver');
// Ensure fetch exists on older Node versions
const fetch = global.fetch || require('node-fetch');

const app = express();

app.use(express.json());

// CORS: allow only configured origins (or '*')
const allowedOrigins = (process.env.CORS_ORIGIN || 'http://localhost:5173')
  .split(',')
  .map((o) => o.trim())
  .filter(Boolean);

const corsOptions = {
  origin: function (origin, callback) {
    // Allow when '*' is set, or exact origin match; otherwise block
    if (!origin) return callback(null, allowedOrigins.includes('*'));
    const allowed = allowedOrigins.includes('*') || allowedOrigins.includes(origin);
    if (!allowed) {
      console.warn(`[middleware] CORS blocked origin: ${origin}`);
    }
    return callback(null, allowed);
  },
  methods: ['GET', 'POST', 'OPTIONS'],
  allowedHeaders: ['Content-Type', 'Authorization'],
  credentials: false,
  optionsSuccessStatus: 204,
};

// Apply CORS and handle preflight for specific routes (Express 5 disallows '*')
app.use(cors(corsOptions));
app.options('/avalie', cors(corsOptions));

const PORT = parseInt(process.env.PORT, 10) || 3001;
const ENGINE_URL = process.env.ENGINE_URL || 'http://localhost:5000/analyze';

// Proxy route called by the frontend
app.post('/avalie', async (req, res) => {
  try {
    const { url } = req.body || {};
    if (!url) {
      return res
        .status(400)
        .json({ status: 'error', message: "Campo 'url' é obrigatório" });
    }
    console.log(`[middleware] Receiving URL to analyze: ${url}`);
    console.log(`[middleware] Forwarding to engine: ${ENGINE_URL}`);

    const response = await fetch(ENGINE_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url }),
    });

    if (!response.ok) {
      throw new Error(
        `Erro ao chamar a engine SEO: ${response.status} ${response.statusText}`
      );
    }

    const data = await response.json();

    const content =
      data?.optimizedContent ||
      data?.content ||
      data?.summary ||
      data?.message ||
      '';

    const files = Array.isArray(data?.files) ? data.files : [];

    const wantZip = req.query?.zip === '1' || req.query?.zip === 'true';
    if (wantZip) {
      res.setHeader('Content-Type', 'application/zip');
      res.setHeader('Content-Disposition', 'attachment; filename="analysis.zip"');

      const archive = archiver('zip', { zlib: { level: 9 } });
      archive.on('error', (err) => {
        console.error('Zip error:', err);
        if (!res.headersSent) {
          res.status(500);
        }
        res.end();
      });
      archive.pipe(res);

      archive.append((content || '').toString(), { name: 'content.txt' });
      archive.append(Buffer.from(JSON.stringify(data, null, 2)), { name: 'engineResponse.json' });

      if (Array.isArray(files)) {
        for (const f of files) {
          const name = (f && f.filename) ? String(f.filename) : 'file.json';
          const payload = JSON.stringify(f?.data ?? f, null, 2);
          archive.append(Buffer.from(payload), { name });
        }
      }

      await archive.finalize();
      return; // streamed
    }

    return res.json({
      status: 'success',
      analyzedUrl: url,
      content,
      files,
      engineResponse: data,
    });
  } catch (error) {
    console.error('Erro na rota /avalie:', error);
    return res.status(500).json({
      status: 'error',
      message: 'Falha ao processar a análise',
      details: error instanceof Error ? error.message : String(error),
    });
  }
});

app.get('/health', (_req, res) => res.json({ status: 'ok' }));

app.listen(PORT, () => console.log(`Middleware SEO rodando na ${PORT}`));
