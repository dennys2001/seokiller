const express = require("express");
const cors = require("cors");

const app = express();

app.use(cors());
app.use(express.json());

// Essa é a rota chamada pelo front
app.post("/avalie", async (req, res) => {
  try {
    // 1. Pega a URL enviada pelo front
    const { url } = req.body;
    if (!url) {
      return res.status(400).json({ status: "error", message: "Campo 'url' é obrigatório" });
    }

    // 2. Chama a engine SEO, passando a URL recebida
    const ENGINE_URL = "http://localhost:5000/analyze"; // substitui pelo endpoint da tua engine

    const response = await fetch(ENGINE_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }) // manda o mesmo formato que o front te mandou
    });

    if (!response.ok) {
      throw new Error(`Erro ao chamar a engine SEO: ${response.status} ${response.statusText}`);
    }

    // 3. Lê o resultado da engine
    const data = await response.json();
    console.log(`✅ URL avaliada com sucesso: ${url}`);
    // 4. Devolve para o front 
    return res.json({
      status: "success",
      analyzedUrl: url,
      engineResponse: data
    });

  } catch (error) {
    console.error("Erro na rota /avalie:", error);
    return res.status(500).json({
      status: "error",
      message: "Falha ao processar a análise",
      details: error.message
    });
  }
});

app.listen(3001, () => console.log("Middleware SEO rodando na 3001"));
