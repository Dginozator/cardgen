#!/bin/sh
set -eu

: "${DIRECTUS_UPSTREAM:?DIRECTUS_UPSTREAM is required}"
: "${N8N_UPSTREAM:?N8N_UPSTREAM is required}"

# Generate nginx config with envsubst (runs before default 20-envsubst-on-templates.sh
# but we use our own script to control exactly which vars are substituted)
envsubst '${DIRECTUS_UPSTREAM} ${N8N_UPSTREAM} ${WORKER_UPSTREAM}' \
  < /etc/nginx/templates/default.conf.template \
  > /etc/nginx/conf.d/default.conf

echo "nginx config generated successfully"