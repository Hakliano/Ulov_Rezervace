!/usr/bin/env bash
# VystavĂ­ Let's Encrypt cert pro modernik.cz (+ www + staging) a zapne HTTPS vhost.
set -euo pipefail
cd "$(dirname "$0")/.."

CONF_FULL=deploy/nginx/conf.d/modernik.conf
CONF_HTTP=deploy/nginx/conf.d/modernik-http-only.conf

echo "=== 1) DoÄŤasnĂ˝ HTTP-only vhost (ACME; bez SSL souborĹŻ) ==="
if [ -f "$CONF_FULL" ]; then
  mv -f "$CONF_FULL" "${CONF_FULL}.pending"
fi

cat > "$CONF_HTTP" <<'EOC'
# DoÄŤasnĂ˝ â€” smaĹľe issue-modernik-cert.sh po vystavenĂ­ certu
server {
    listen 80;
    server_name modernik.cz www.modernik.cz staging.modernik.cz;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 200 'modernik acme ready\n';
        add_header Content-Type text/plain;
    }
}
EOC

mkdir -p www/modernik www-staging/modernik
if [ ! -f www/modernik/index.html ] && [ -f www-staging/modernik/index.html ]; then
  rsync -a www-staging/modernik/ www/modernik/
fi

docker compose exec -T nginx nginx -t
docker compose exec -T nginx nginx -s reload

echo "=== 2) Certbot webroot ==="
docker compose run --rm --entrypoint certbot certbot certonly \
  --webroot -w /var/www/certbot \
  --cert-name modernik.cz \
  --non-interactive --agree-tos \
  --email "${CERTBOT_EMAIL:-info@ulovklienty.cz}" \
  -d modernik.cz \
  -d www.modernik.cz \
  -d staging.modernik.cz

echo "=== 3) Zapnout plnĂ˝ HTTPS conf ==="
if [ -f "${CONF_FULL}.pending" ]; then
  mv -f "${CONF_FULL}.pending" "$CONF_FULL"
elif [ -f "${CONF_FULL}.disabled" ]; then
  mv -f "${CONF_FULL}.disabled" "$CONF_FULL"
fi
rm -f "$CONF_HTTP"

# Obnov conf ze gitu pokud pending chybĂ­ (napĹ™. po ruÄŤnĂ­m zĂˇsahu)
if [ ! -f "$CONF_FULL" ] && [ -f deploy/nginx/conf.d/modernik.conf.pending ]; then
  mv -f deploy/nginx/conf.d/modernik.conf.pending "$CONF_FULL"
fi

docker compose exec -T nginx nginx -t
docker compose exec -T nginx nginx -s reload

echo "=== Smoke ==="
curl -sS -o /dev/null -w "staging_ulov:%{http_code}\n" "https://www.staging.ulovklienty.cz/" || true
curl -sS -o /dev/null -w "staging_modernik:%{http_code}\n" "https://staging.modernik.cz/" || true
curl -sS -o /dev/null -w "www_modernik:%{http_code}\n" "https://www.modernik.cz/" || true
echo "=== Hotovo ==="
