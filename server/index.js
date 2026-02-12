require('dotenv').config();

const express = require('express');
const cors = require('cors');
const archiver = require('archiver');
// Ensure fetch exists on older Node versions
const fetch = global.fetch || require('node-fetch');

const app = express();

app.use(express.json());

// CORS: allow only configured origins (or '*')
const allowedOrigins = process.env.CORS_ORIGIN.split(',');
 //.split(',')
 //.map((o) => o.trim())
 // .filter(Boolean);

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
  allowedHeaders: ['Content-Type', 'Authorization', 'x-wce-key'],
  credentials: false,
  optionsSuccessStatus: 204,
};

// Apply CORS and handle preflight for specific routes (Express 5 disallows '*')
app.use(cors(corsOptions));
app.options('/avalie', cors(corsOptions));

const PORT = parseInt(process.env.PORT, 10) || 3001;
const ENGINE_URL = process.env.ENGINE_URL || 'http://localhost:5000/analyze';
const ENGINE_TIMEOUT_MS =
  parseInt(process.env.ENGINE_TIMEOUT_MS, 10) || 180_000;
const SHARED_KEY = (process.env.WCE_SHARED_KEY || '').trim();

const trimUrl = (value) =>
  typeof value === 'string' ? value.trim() : '';

const isHttpUrl = (value) => /^https?:\/\//i.test(value);
const asPositiveInt = (value) => {
  const n = Number(value);
  return Number.isInteger(n) && n > 0 ? n : null;
};
const asPositiveNumber = (value) => {
  const n = Number(value);
  return Number.isFinite(n) && n > 0 ? n : null;
};

async function readEnginePayload(response) {
  const raw = await response.text();
  if (!raw) {
    return { raw: '', json: null };
  }
  try {
    return { raw, json: JSON.parse(raw) };
  } catch (err) {
    console.warn('[middleware] Engine returned non-JSON payload');
    return { raw, json: null };
  }
}

function sendError(res, status, message, extra = {}) {
  res.statusMessage = message;
  return res.status(status).json({
    status: 'error',
    message,
    ...extra,
  });
}

function isAuthorized(req) {
  if (!SHARED_KEY) return true;
  const key = req.header('x-wce-key');
  return typeof key === 'string' && key === SHARED_KEY;
}

function friendlyEngineMessage(originalMessage, url) {
  if (!originalMessage) {
    return 'Nao foi possivel processar a URL informada';
  }
  const text = originalMessage.toLowerCase();
  if (
    text.includes('falha ao buscar url') ||
    text.includes('name resolution') ||
    text.includes('getaddrinfo') ||
    text.includes('failed to resolve')
  ) {
    return `Nao foi possivel acessar ${url}. Confirme se o endereco existe e tente novamente.`;
  }
  if (text.includes('timeout') || text.includes('timed out')) {
    return `A conexao com ${url} demorou demais. Tente novamente em instantes.`;
  }
  return originalMessage;
}

// Proxy route called by the frontend
app.post('/avalie', async (req, res) => {
  try {
    if (!isAuthorized(req)) {
      return sendError(res, 401, 'Chave de acesso invalida');
    }
    const normalizedUrl = trimUrl(req.body?.url);
    if (!normalizedUrl) {
      return sendError(res, 400, "Informe uma URL antes de continuar");
    }
    if (!isHttpUrl(normalizedUrl)) {
      return sendError(
        res,
        400,
        "URL invalida. Use enderecos iniciando com http:// ou https://"
      );
    }
    console.log(`[middleware] Receiving URL to analyze: ${normalizedUrl}`);
    console.log(`[middleware] Forwarding to engine: ${ENGINE_URL}`);

    const controller = new AbortController();
    const timeoutId = setTimeout(
      () => controller.abort(),
      ENGINE_TIMEOUT_MS
    );

    const useCrawler = !!req.body?.useCrawler;
    const payload = { url: normalizedUrl, useCrawler };

    // Forward crawler tunables when provided by the client.
    if (useCrawler) {
      const maxPages = asPositiveInt(req.body?.maxPages);
      const maxTasks = asPositiveInt(req.body?.maxTasks);
      const timeout = asPositiveInt(req.body?.timeout);
      const delay = asPositiveNumber(req.body?.delay);
      if (maxPages !== null) payload.maxPages = maxPages;
      if (maxTasks !== null) payload.maxTasks = maxTasks;
      if (timeout !== null) payload.timeout = timeout;
      if (delay !== null) payload.delay = delay;
    }

    let response;
    try {
      response = await fetch(ENGINE_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        signal: controller.signal,
      });
    } finally {
      clearTimeout(timeoutId);
    }

    let { json: data, raw } = await readEnginePayload(response);

    // If crawler fails (common on anti-bot / maintenance), do not break the UI.
    // Fallback to non-crawler analysis and attach a warning.
    if (!response.ok && useCrawler) {
      const errText =
        (data && typeof data === 'object' && data.message ? String(data.message) : String(raw || '')).toLowerCase();
      const looksBlocked =
        errText.includes('anti-bot') ||
        errText.includes('captcha') ||
        errText.includes('manut') ||
        errText.includes('bloque') ||
        response.status === 403 ||
        response.status === 429 ||
        response.status === 502 ||
        response.status === 504;

      if (looksBlocked) {
        console.warn('[middleware] Crawler failed; retrying engine without crawler (summary fallback).');

        const fallbackController = new AbortController();
        const fallbackTimeoutId = setTimeout(() => fallbackController.abort(), ENGINE_TIMEOUT_MS);
        let fallbackResp;
        try {
          fallbackResp = await fetch(ENGINE_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url: normalizedUrl, useCrawler: false }),
            signal: fallbackController.signal,
          });
        } finally {
          clearTimeout(fallbackTimeoutId);
        }

        const fallbackPayload = await readEnginePayload(fallbackResp);
        if (fallbackResp.ok && fallbackPayload.json && typeof fallbackPayload.json === 'object') {
          response = fallbackResp;
          data = fallbackPayload.json;
          raw = fallbackPayload.raw;
          data.warning =
            data.warning ||
            'Site protegido por anti-bot ou em manutencao. Nao foi possivel realizar analise completa com crawler; exibindo somente resumo.';
          data.mode = data.mode || 'crawler_fallback_summary';
        }
      }
    }

    if (!response.ok) {
      const status =
        response.status >= 400 && response.status < 500
          ? response.status
          : 502;
      const message =
        data && typeof data === 'object' && data.message
          ? data.message
          : `Engine retornou ${response.status} ${response.statusText}`;
      const friendlyMessage = friendlyEngineMessage(message, normalizedUrl);
      return sendError(res, status, friendlyMessage, {
        engineStatus: response.status,
        engineResponse: data ?? raw,
        debugMessage: message,
      });
    }

    if (!data || typeof data !== 'object') {
      return sendError(res, 502, 'Engine respondeu com formato inesperado', {
        engineResponse: raw,
      });
    }

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
      analyzedUrl: data?.analyzedUrl || normalizedUrl,
      content,
      files,
      engineResponse: data,
    });
  } catch (error) {
    console.error('Erro na rota /avalie:', error);
    const isAbort = error?.name === 'AbortError';
    const status = isAbort ? 504 : 502;
    const message = isAbort
      ? 'Tempo de resposta esgotado ao contatar a engine'
      : 'Nao foi possivel contatar a engine SEO';
    return sendError(res, status, message, {
      details: error instanceof Error ? error.message : String(error),
    });
  }
});

app.get('/health', (_req, res) => res.json({ status: 'ok' }));

// Export app for tests; only listen when run directly
if (require.main === module) {
  app.listen(PORT, () => console.log(`Middleware SEO rodando na ${PORT}`));
}

module.exports = { app };
