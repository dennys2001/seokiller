// engine.js
require('dotenv').config();

const express = require('express');
const app = express();
app.use(express.json());

app.post('/analyze', (req, res) => {
  const { url } = req.body || {};
  console.log('Recebido pra análise:', url);

  // Mock realistic payload: textual summary plus multiple JSON files
  const summary = `Análise concluída para ${url}. Título presente, meta description ausente, 3 H2 encontrados.`;

  const files = [
    {
      filename: 'summary.json',
      mimeType: 'application/json',
      data: {
        url,
        score: 92,
        issues: [
          { type: 'meta', message: 'Meta description ausente' },
          { type: 'images', message: '2 imagens sem atributo alt' },
        ],
      },
    },
    {
      filename: 'headings.json',
      mimeType: 'application/json',
      data: {
        title: 'Título de Exemplo',
        h1: ['Título Principal'],
        h2: ['Seção 1', 'Seção 2', 'Seção 3'],
      },
    },
    {
      filename: 'meta.json',
      mimeType: 'application/json',
      data: {
        description: null,
        descriptionLength: 0,
      },
    },
    {
      filename: 'links.json',
      mimeType: 'application/json',
      data: {
        internal: ['/', '/contato', '/blog'],
        external: ['https://example.com'],
      },
    },
  ];

  res.json({ analyzedUrl: url, summary, files });
});

const PORT = parseInt(process.env.ENGINE_PORT, 10) || 5000;
app.listen(PORT, () => console.log(`Engine falsa rodando na ${PORT}`));
