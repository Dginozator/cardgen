# Deployment (Dokploy)

This branch is prepared for a Dokploy deployment from Git repository.

## Services

- `nuxt` - frontend app
- `nginx` - public entrypoint and reverse proxy

## Proxy contract

- `https://app.example.com/api/d/*` -> Directus upstream
- `https://app.example.com/api/n/*` -> n8n upstream

Real upstream hostnames are kept in environment variables and are not exposed in frontend code.

## Dokploy setup

1. Create a new project in Dokploy from this repository.
2. Select Compose deployment and use `docker-compose.yml`.
3. Set environment variables from `.env.example`.
4. Publish the `nginx` service through Dokploy built-in reverse proxy and bind your domain.
5. Deploy.

## Required variables

- `APP_DOMAIN`
- `DIRECTUS_UPSTREAM`
- `N8N_UPSTREAM`

## Optional variables

- `NUXT_PUBLIC_API_BASE` (default `/api`)
- `NUXT_PUBLIC_DIRECTUS_BASE` (default `/api/d`)
- `NUXT_PUBLIC_N8N_BASE` (default `/api/n`)

## Local smoke test

```bash
cp .env.example .env
docker compose up --build
```

Open `http://localhost:8080`.

For Dokploy production deployment, no host port mapping is required in Compose.
