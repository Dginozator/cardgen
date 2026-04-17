# Cardgen - directus_gen

This branch is prepared as a deployable repository for Dokploy:

- Nuxt frontend service
- Nginx reverse proxy service
- Hidden upstream routing:
  - `/api/d/*` -> Directus
  - `/api/n/*` -> n8n

Public users only see your app domain (`app.example.com`) and internal API prefixes.

## Deploy model

- Frontend is served by Nuxt (`web/`).
- Nginx is the public entrypoint and proxy layer.
- Real upstream hosts are configured via environment variables only.

## Quick start (local)

```bash
cp .env.example .env
docker compose up --build
```

Open `http://localhost:8080`.

## Dokploy

Use Compose deployment with `docker-compose.yml`, then set environment variables from `.env.example`.

Detailed steps: `DEPLOYMENT.md`.

## Branch content

- `web/` - Nuxt app skeleton
- `nginx/` - reverse proxy config template
- `docker-compose.yml` - deployment topology
- `DEPLOYMENT.md` - operational setup guide
- `info/`, `PLAN.md`, `BACKLOG.md`, `samples/` - product and research documents
