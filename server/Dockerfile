FROM node:18-alpine

WORKDIR /app

# Copia os manifests e instala somente as dependências de produção
COPY package*.json ./
RUN if [ -f package-lock.json ]; then npm ci --omit=dev; else npm install --omit=dev; fi

# Copia o restante do código do middleware
COPY . .

ENV NODE_ENV=production
ENV CORS_ORIGIN=http://localhost:4173

EXPOSE 3001

CMD ["node", "index.js"]
