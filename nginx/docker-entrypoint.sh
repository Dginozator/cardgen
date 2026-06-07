#!/bin/sh
set -eu

: "${DIRECTUS_UPSTREAM:?DIRECTUS_UPSTREAM is required}"
: "${N8N_UPSTREAM:?N8N_UPSTREAM is required}"

# Wait for Nuxt app DNS and HTTP endpoint to be reachable before nginx starts.
# This avoids boot-time race conditions in orchestrated environments.
i=0
until wget -q -T 2 -t 1 -O- "http://nuxt:3000/" >/dev/null 2>&1; do
  i=$((i + 1))
  echo "waiting for nuxt upstream (${i}/60): http://nuxt:3000/"
  if [ "$i" -ge 60 ]; then
    echo "nuxt upstream is not reachable after 60s: http://nuxt:3000/"
    exit 1
  fi
  sleep 1
done

envsubst '${DIRECTUS_UPSTREAM} ${N8N_UPSTREAM}' \
  < /etc/nginx/templates/default.conf.template \
  > /etc/nginx/conf.d/default.conf
