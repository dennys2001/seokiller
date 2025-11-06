# SEO Optimizer - Frontend

Interface simples para análise e otimização de conteúdo SEO.

## 🚀 Como rodar localmente

### Pré-requisitos
- Node.js (versão 16 ou superior)
- npm ou yarn

### Instalação

1. **Instale as dependências:**
```bash
npm install
```

2. **Configure a URL do seu engine:**
   
   Abra o arquivo `App.tsx` e altere a linha 14:
   ```typescript
   const ENGINE_URL = 'http://localhost:3000/api/analyze'; // Coloque a URL do seu engine aqui
   ```

3. **Inicie o servidor de desenvolvimento:**
```bash
npm run dev
```

O aplicativo estará rodando em `http://localhost:5173`

### Build para produção

```bash
npm run build
```

Os arquivos otimizados estarão na pasta `dist/`

Para visualizar o build de produção:
```bash
npm run preview
```

## 📝 Configuração do Engine

O frontend envia um POST request para o seu engine no seguinte formato:

**Request:**
```json
{
  "url": "https://exemplo.com"
}
```

**Response esperada:**
O frontend procura por uma das seguintes propriedades na resposta JSON:
- `optimizedContent`
- `content`
- `result`

Se nenhuma dessas propriedades existir, ele exibe o JSON completo formatado.

Ajuste a linha 40 do `App.tsx` se seu engine retornar em um campo diferente.

## 🎨 Funcionalidades

- ✅ Interface minimalista estilo Google
- ✅ Campo de input para URL
- ✅ Botão de envio com loading state
- ✅ Box de resultado com scroll
- ✅ Botão copiar conteúdo
- ✅ Tratamento de erros
- ✅ Suporte a Enter para enviar

## 🛠️ Tecnologias

- React 18
- TypeScript
- Vite
- Tailwind CSS v4
- Shadcn/ui components
- Lucide Icons
