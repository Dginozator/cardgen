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

- `DIRECTUS_UPSTREAM`
- `N8N_UPSTREAM`

## Optional variables

- `NUXT_PUBLIC_API_BASE` (default `/api`)
- `NUXT_PUBLIC_DIRECTUS_BASE` (default `/api/d`)
- `NUXT_PUBLIC_N8N_BASE` (default `/api/n`)
- `NUXT_PUBLIC_DIRECTUS_RESET_URL` (default `<current-origin>/reset-password`)

### Directus registration email

Registration always sends `verification_url` as `<current-browser-origin>/verify-email` (no extra frontend env). Directus **`USER_REGISTER_URL_ALLOW_LIST`** must include every origin you use in production, e.g. `https://wb.dginozator.com/verify-email`.

**`PUBLIC_URL` on the Directus server** should match where **admins** open Directus. End users complete verification from Nuxt via `GET /users/register/verify-email` through `/api/d`.

## Local smoke test

```bash
cp .env.example .env
docker compose up --build
```

Open `http://localhost:8080`.

For Dokploy production deployment, no host port mapping is required in Compose.
