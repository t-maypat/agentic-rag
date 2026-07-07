# Loupe frontend — build with Vite, serve static via nginx (REVAMP_PLAN §13).
# Build context is the repo root (see docker-compose.yml).

# ---- Stage 1: build the Vite bundle ----
FROM node:20-alpine AS build

WORKDIR /app
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci || npm install

COPY frontend/ ./
# Empty API base → same-origin "/api/..." requests, proxied to the backend by
# nginx (see nginx.conf). Overridable at build time for other deployments.
ARG VITE_API_BASE_URL=""
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

# ---- Stage 2: nginx static server + /api proxy ----
FROM nginx:alpine

COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
