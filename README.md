# Cardgen (`directus_gen`)

**Основная ветка разработки — `directus_gen`.** Остальные ветки (`main`, `extgen`, `rembg` и др.) — побочные: интеграция, старые версии, эксперименты; **котируется только тег-лейбл** ниже, если нужен зафиксированный снимок для нового репозитория.

This branch is prepared as a deployable repository for Dokploy:

- Nuxt frontend service
- Nginx reverse proxy service
- Hidden upstream routing:
  - `/api/d/*` -> Directus
  - `/api/n/*` -> n8n

Public users only see your app domain (`app.example.com`) and internal API prefixes.

## Шаблон нового репозитория (`template/v1.0.0`)

Снимок для форков и новых проектов — **только** тег **`template/v1.0.0`**:

```bash
git clone https://github.com/Dginozator/cardgen.git
cd cardgen
git checkout template/v1.0.0
```

Тег указывает на фиксированный коммит и не следует за `directus_gen`. Актуальный код — в ветке **`directus_gen`**.

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
- `PLAN.md`, `BACKLOG.md`, `samples/` - product and research documents (локальные заметки в `info/` не в репозитории — см. `.gitignore`)
