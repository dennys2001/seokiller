require('dotenv').config();

const express = require('express');
const cors = require('cors');

const app = express();

app.use(express.json());

// CORS tightening: only allow configured origins (comma-separated)
const allowedOrigins = (process.env.CORS_ORIGIN || 'http://localhost:5173')
  .split(',')
  .map((o) => o.trim())
  .filter(Boolean);

app.use(
  cors({
    origin: function (origin, callback) {
      // Disallow requests without Origin; allow '*' or explicit matches
      if (!origin) return callback(null, false);
      if (allowedOrigins.includes('*') || allowedOrigins.includes(origin)) {
        return callback(null, true);
      }
      return callback(null, false);
    },
    methods: ['GET', 'POST', 'OPTIONS'],
    optionsSuccessStatus: 204,
  })
);

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
    return res.json({ status: 'success', analyzedUrl: url, engineResponse: data });
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

