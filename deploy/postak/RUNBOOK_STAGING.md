# Pošťák — runbook nasazení na STAGING (Hetzner)

**Schválená URL:** `https://www.staging.ulovklienty.cz/postak/`  
**Nepouštět** na LIVE. **Neměnit** LIVE nginx / MAIN bez schválení.

---

## 0. Předpoklady

- `origin/dev` obsahuje Pošťák + Postak API (viz poslední commity).
- SSH na VPS (stejný host jako Ulov staging stack).
- Síť Docker `ulov_default` existuje (běží hlavní compose).
- Soubor `postak/.env` na serveru (z `.env.staging.example`, **mimo git**).

---

## 1. SSH — host key (`Host key verification failed`)

**Příčina v Cursor/Windows:** klíč serveru není v `~/.ssh/known_hosts`, nebo OpenSSH odmítá KEX (`sntrup761…`) při `ssh-keyscan`.

**Bezpečné ověření (doporučeno):**

1. V **Hetzner Cloud Console** → server → **SSH keys** / rescue: ověřte IP a fingerprint klíče hostitele (ed25519).
2. Na svém PC (Git Bash nebo WSL, pokud Windows ssh-keyscan selže):

```bash
ssh-keyscan -H www.staging.ulovklienty.cz >> ~/.ssh/known_hosts
# nebo přes IP serveru:
ssh-keyscan -H YOUR_VPS_IP >> ~/.ssh/known_hosts
```

3. Porovnejte fingerprint s Hetznerem / prvním ručním přihlášením:

```bash
ssh -o StrictHostKeyChecking=accept-new root@YOUR_VPS_IP
ssh-keygen -lf ~/.ssh/known_hosts | grep staging
```

4. V `~/.ssh/config` (volitelně):

```
Host ulov-staging
    HostName YOUR_VPS_IP
    User root
    StrictHostKeyChecking yes
    KnownHostsFile ~/.ssh/known_hosts
```

**Nikdy** nevypínejte `StrictHostKeyChecking` trvale na produkci.

---

## 2. Git na serveru

```bash
cd /opt/ulov   # nebo váš checkout
git fetch origin
git checkout dev && git pull origin dev
git log -1 --oneline
```

Očekávaně commity obsahující `postak/` a `postak_api`.

---

## 3. Nginx (až po schválení nasazení — ruční krok)

Do `deploy/nginx/conf.d/staging.conf` v `server { server_name www.staging.ulovklienty.cz ... }` vložit obsah  
`deploy/postak/nginx-staging-snippet.conf` **před** `location / { try_files …`.

**Kolize:** na staging hubu **není** statická složka `/postak/` — cesta je volná (regex dema: `/salonN/`, `/flow/`, `/sklad/`, …).

Ověření konfigurace (na serveru, **jen staging** kontejner nginx — dle vašeho stacku):

```bash
docker exec ulov-nginx nginx -t
docker exec ulov-nginx nginx -s reload
```

Rollback nginx: odstranit vložený blok `location /postak/` a znovu `reload`.

---

## 4. Secrets — `postak/.env`

```bash
cp postak/.env.staging.example postak/.env
nano postak/.env   # SECRET_KEY, POSTGRES_PASSWORD, POSTAK_BUNNY_*, tokeny STAGING API
chmod 600 postak/.env
```

- `MODERNIK_API_BASE=https://api-staging.ulovklienty.cz/partner-admin/api/postak/v1`
- `POSTAK_BUNNY_ROOT_PREFIX=postak/staging`
- Backend staging musí mít `POSTAK_POTENCIALNI_API_TOKEN` shodný s `MODERNIK_API_TOKEN` v Pošťáku.

---

## 5. Deploy Pošťák (compose)

```bash
bash deploy/postak/deploy-staging-postak.sh origin/dev
```

Ručně ekvivalent:

```bash
docker compose -p postak-staging -f postak/docker-compose.staging.yml --env-file postak/.env up -d --build
docker compose -p postak-staging -f postak/docker-compose.staging.yml --env-file postak/.env exec web python manage.py migrate --noinput
docker compose -p postak-staging -f postak/docker-compose.staging.yml --env-file postak/.env exec web python manage.py postak_bunny_smoke
```

**Kontrola:**

```bash
curl -sS -o /dev/null -w "%{http_code}\n" https://www.staging.ulovklienty.cz/postak/prihlaseni/
# očekávání: 200
docker ps --filter name=ulov-staging-postak
docker compose -p postak-staging ps
```

První superuser (jednorázově):

```bash
docker compose -p postak-staging -f postak/docker-compose.staging.yml --env-file postak/.env exec web \
  python manage.py createsuperuser
```

---

## 6. Moderník API (staging backend)

Po deployi **hlavního** staging API (existující `deploy-staging.sh`), pokud ještě není:

```bash
# v /opt/ulov — váš staging stack
docker compose -p ulov-staging -f docker-compose.staging.yml --env-file .env.staging exec staging-api \
  python manage.py migrate partner_admin
```

Do `.env.staging` na backendu přidat **staging-only** token (ne LIVE):

`POSTAK_POTENCIALNI_API_TOKEN=<stejné jako MODERNIK_API_TOKEN v postak/.env>`

---

## 7. Rollback

**Pošťák pouze:**

```bash
docker compose -p postak-staging -f postak/docker-compose.staging.yml --env-file postak/.env down
# obnova DB z zálohy:
docker compose -p postak-staging -f postak/docker-compose.staging.yml --env-file postak/.env --profile backup run --rm backup
# restore: pg_restore … do postak_staging_pgdata (viz Postgres docs)
```

**Git na starší revizi:**

```bash
git checkout <previous-sha>
bash deploy/postak/deploy-staging-postak.sh HEAD
```

**Nginx:** odebrat snippet, `nginx -s reload`.

Bunny: soubory pod `postak/staging/` — záloha `python manage.py postak_bunny_backup`.

---

## 8. Infrastruktura (souhrn)

| Položka | Hodnota |
|---------|---------|
| Compose project | `postak-staging` |
| Kontejner web | `ulov-staging-postak` |
| Postgres volume | `postak_staging_pgdata` |
| Síť | `ulov_live` → `ulov_default` (external) |
| Není sdíleno | Ulov staging DB, Materiálník volume, LIVE |
