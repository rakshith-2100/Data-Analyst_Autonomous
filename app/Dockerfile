# Frontend: build the Vite SPA, then serve it (and reverse-proxy /api) with Caddy.
FROM node:20-alpine AS build
WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
# Same-origin deploy: the SPA calls the backend through a relative /api prefix,
# which Caddy strips and forwards to the backend container (see Caddyfile).
ENV VITE_API=/api
RUN npm run build

FROM caddy:2-alpine
COPY Caddyfile /etc/caddy/Caddyfile
COPY --from=build /app/dist /srv
