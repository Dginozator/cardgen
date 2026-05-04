# Cardgen (`directus_gen`)

**Primary development branch: `directus_gen`.** Other branches (`main`, `extgen`, `rembg`, etc.) are secondary (integration, legacy, experiments). For a **pinned baseline** to start a new repository, use **only** the **`template/v1.0.0`** tag below.

This branch is prepared as a deployable repository for Dokploy:

- Nuxt frontend service
- Nginx reverse proxy service
- Hidden upstream routing:
  - `/api/d/*` -> Directus
  - `/api/n/*` -> n8n

Public users only see your app domain (`app.example.com`) and internal API prefixes.

## New repository template (`template/v1.0.0`)

For forks and new projects, use **only** the **`template/v1.0.0`** tag:

```bash
git clone https://github.com/Dginozator/cardgen.git
cd cardgen
git checkout template/v1.0.0
```

The tag points at a fixed commit and does not advance with `directus_gen`. Current product code lives on **`directus_gen`**.

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
- `PLAN.md`, `BACKLOG.md`, `samples/` - product and research documents (local notes under `info/` are not versioned — see `.gitignore`)
