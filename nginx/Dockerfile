FROM nginx:1.27-alpine

RUN apk add --no-cache gettext

COPY default.conf.template /etc/nginx/templates/default.conf.template
COPY docker-entrypoint.sh /docker-entrypoint.d/99-render-config.sh

RUN chmod +x /docker-entrypoint.d/99-render-config.sh
