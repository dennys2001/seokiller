FROM node:20-alpine AS build

WORKDIR /app

COPY package*.json ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

COPY . .

ARG VITE_API_URL=/avalie
ARG VITE_WCE_KEY=
ENV VITE_API_URL=$VITE_API_URL
ENV VITE_WCE_KEY=$VITE_WCE_KEY

RUN npm run build

FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf.template /etc/nginx/templates/default.conf.template

# Defaults for local docker-compose; override in the runtime environment for production.
ENV WCS_BACKEND_URL=http://server:3001/avalie
ENV WCS_SHARED_KEY=super-secret-key

EXPOSE 80
