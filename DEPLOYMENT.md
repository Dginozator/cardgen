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
- `NUXT_PUBLIC_DIRECTUS_VERIFY_URL` (default `<current-origin>/verify-email`)

### Directus registration email (production)

Registration `verification_url` is sent from the Nuxt app (see `useDirectusAuth`). In Directus, **`USER_REGISTER_URL_ALLOW_LIST`** must include the exact URL users open in the email, e.g. `https://wb.dginozator.com/verify-email`. Set **`NUXT_PUBLIC_DIRECTUS_VERIFY_URL`** to that same URL if the app origin must be explicit.

**`PUBLIC_URL` on the Directus server** should match where **admins** open Directus (e.g. `https://directus.dginozator.com`). End users stay on the Nuxt host; verification is completed via a manual-fetch call from Nuxt to `GET /users/register/verify-email` through `/api/d`, not by sending users to the Directus admin UI on Nuxt.

## Local smoke test

```bash
cp .env.example .env
docker compose up --build
```

Open `http://localhost:8080`.

For Dokploy production deployment, no host port mapping is required in Compose.
