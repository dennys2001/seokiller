# 📦 Instruções para Download e Execução Local

## Passo a Passo

### 1️⃣ Baixar o projeto
Baixe todos os arquivos do projeto para uma pasta local no seu computador.

### 2️⃣ Abrir terminal na pasta do projeto
Abra o terminal/prompt de comando na pasta onde você baixou os arquivos.

### 3️⃣ Instalar dependências
```bash
npm install
```

Isso irá instalar todas as bibliotecas necessárias (React, Tailwind, etc.)

### 4️⃣ Configurar a URL do seu Engine
Abra o arquivo `App.tsx` e na **linha 14**, altere para a URL do seu engine:

```typescript
const ENGINE_URL = 'http://seu-servidor.com/api/analyze';
```

### 5️⃣ Rodar o projeto
```bash
npm run dev
```

O navegador deve abrir automaticamente em `http://localhost:5173`

---

## ⚙️ Configurações do Engine

### O que o frontend envia:
```json
POST /sua-rota
Content-Type: application/json

{
  "url": "https://site-do-usuario.com"
}
```

### O que o frontend espera receber:
```json
{
  "optimizedContent": "Seu texto otimizado aqui..."
}
```

**OU**

```json
{
  "content": "Seu texto otimizado aqui..."
}
```

**OU**

```json
{
  "result": "Seu texto otimizado aqui..."
}
```

Se o seu engine retornar com um nome de campo diferente, edite a **linha 40** do `App.tsx`:

```typescript
setResult(data.SEU_CAMPO_AQUI);
```

---

## 🔧 Estrutura do Projeto

```
/
├── App.tsx                    # Componente principal
├── main.tsx                   # Entry point
├── index.html                 # HTML base
├── package.json               # Dependências
├── vite.config.ts            # Configuração Vite
├── tsconfig.json             # Configuração TypeScript
├── styles/
│   └── globals.css           # Estilos globais e Tailwind
└── components/
    └── ui/                   # Componentes Shadcn/ui
        ├── button.tsx
        ├── input.tsx
        ├── card.tsx
        └── ...
```

---

## 🚨 Troubleshooting

### Problema: "Cannot find module 'react'"
**Solução:** Execute `npm install` novamente

### Problema: Erro de CORS ao chamar o engine
**Solução:** Configure CORS no seu engine Node.js:
```javascript
app.use((req, res, next) => {
  res.header('Access-Control-Allow-Origin', '*');
  res.header('Access-Control-Allow-Headers', 'Content-Type');
  next();
});
```

### Problema: Porta 5173 já está em uso
**Solução:** Mude a porta no `vite.config.ts` ou feche o processo que está usando a porta 5173

---

## 📞 Dúvidas?

- Certifique-se de que o Node.js está instalado: `node --version`
- Certifique-se de que o npm está instalado: `npm --version`
- Verifique se o seu engine está rodando antes de testar

Bom desenvolvimento! 🚀
