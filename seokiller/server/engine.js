// engine.js
require('dotenv').config();

const express = require('express');
const app = express();
app.use(express.json());

app.post('/analyze', (req, res) => {
  const { url } = req.body || {};
  console.log('Recebido pra análise:', url);
  res.json({
    analyzedUrl: url,
    seoScore: 92,
    message: 'Simulação de análise SEO completada.',
  });
});

const PORT = parseInt(process.env.ENGINE_PORT, 10) || 5000;
app.listen(PORT, () => console.log(`Engine falsa rodando na ${PORT}`));

