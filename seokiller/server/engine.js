// engine.js
const express = require("express");
const app = express();
app.use(express.json());

app.post("/analyze", (req, res) => {
  const { url } = req.body;
  console.log("Recebido pra análise:", url);
  res.json({
    analyzedUrl: url,
    seoScore: 92,
    message: "Simulação de análise SEO completada."
  });
});

app.listen(5000, () => console.log("Engine falsa rodando na 5000"));