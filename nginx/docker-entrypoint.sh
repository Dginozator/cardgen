#!/bin/sh
set -eu

: "${DIRECTUS_UPSTREAM:?DIRECTUS_UPSTREAM is required}"
: "${N8N_UPSTREAM:?N8N_UPSTREAM is required}"

envsubst '${APP_DOMAIN} ${DIRECTUS_UPSTREAM} ${N8N_UPSTREAM}' \
  < /etc/nginx/templates/default.conf.template \
  > /etc/nginx/conf.d/default.conf
