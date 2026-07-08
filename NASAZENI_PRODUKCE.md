# ULOV KLIENTY — nasazení do produkce (runbook)

Praktický postup pro nasazení stávajícího řešení **beze změny architektury**.
Cíl: cca 350 salonů (většinou živnostníci, ~2 zaměstnanci) na jednom VPS + PostgreSQL.
Neřešíme Kubernetes/mikroslužby — priorita je stabilita a jednoduchá správa.

Prostředí: **Hetzner VPS + Ubuntu 24.04 + Docker Compose + Nginx + Gunicorn + PostgreSQL 16 + Bunny.net + Let's Encrypt.**

---

## 0. Co je připravené v repu

| Soubor | Účel |
|--------|------|
| `backend/Dockerfile` | Image API (Gunicorn, collectstatic) |
| `docker-compose.yml` | Služby `db`, `api`, `cron`, `nginx`, `certbot` |
| `deploy/nginx/conf.d/ulov.conf` | Reverse proxy + HTTPS |
| `deploy/init-letsencrypt.sh` | Prvotní vydání certifikátu |
| `deploy/backup.sh` | Záloha DB + konfigurace |
| `deploy/restore.sh` | Obnova zálohy (drill i ostrá havárie) |
| `deploy/disk-check.sh` | Hlídání obsazenosti disku (80/90 %) |
| `deploy/loadtest/locustfile.py` | Load test veřejných endpointů |
| `.env.production.example` | Vzor produkčního `.env` |

Backend čte veškerou konfiguraci z prostředí (`.env`). Bez `DB_NAME` běží na SQLite (jen dev),
`DEBUG` je defaultně `False`, `SECRET_KEY` se bere z `.env`.

---

## 1. Server a DNS

1. Vytvořit VPS (doporučeno Hetzner CPX31 / 4 vCPU / 8 GB, Ubuntu 24.04).
2. DNS `A` záznam: `api.vase-domena.cz` → IP serveru. (Domény webů salonů zvlášť, viz sekce 6.)
3. Nainstalovat Docker + Compose plugin:
   ```bash
   curl -fsSL https://get.docker.com | sh
   ```

## 2. Kód a konfigurace

```bash
git clone https://github.com/Hakliano/Ulov_Rezervace.git /opt/ulov
cd /opt/ulov
cp .env.production.example .env
nano .env    # vyplnit SECRET_KEY, DB_PASSWORD, ALLOWED_HOSTS, CORS_*, Bunny, SALON_ADMIN_PASSWORD
```

Nový `SECRET_KEY`:
```bash
docker run --rm python:3.12-slim python -c \
  "from secrets import token_urlsafe; print(token_urlsafe(64))"
```

V `deploy/nginx/conf.d/ulov.conf` nahradit `api.vase-domena.cz` skutečnou doménou.

## 3. Start a migrace databáze

```bash
docker compose up -d --build db api cron
# migrace proběhnou automaticky při startu 'api' (viz command v compose)
docker compose logs -f api      # ověřit "Booting worker"
```

Vytvoření administrátora (Django admin) a inicializačních dat:
```bash
docker compose exec api python manage.py createsuperuser
docker compose exec api python manage.py seed_salons     # jen pokud chcete demo data
docker compose exec api python manage.py check           # kontrola modelů/konfigurace
```

> SQLite se v produkci nepoužívá — přítomnost `DB_NAME` v `.env` přepne na PostgreSQL.

## 4. HTTPS (Let's Encrypt)

```bash
DOMAIN=api.vase-domena.cz EMAIL=vas@email.cz bash deploy/init-letsencrypt.sh
docker compose up -d            # dojede nginx + certbot (automatická obnova)
```

Ověření:
```bash
curl -I https://api.vase-domena.cz/api/    # očekáváme HTTP/2 200/401/403 (ne connection error)
curl https://api.vase-domena.cz/health/    # {"status":"ok","database":"ok"}
```

### Automatická obnova certifikátu

Obnovu řeší služba `certbot` (kontrola 2× denně). Ověřte, že renew funguje:
```bash
docker compose run --rm --entrypoint certbot certbot renew --dry-run
```
Pokud dry-run projde, ostrá obnova i reload Nginxu (12h smyčka) fungují.

## 5. Produkční kontrola konfigurace

```bash
docker compose exec api python manage.py check --deploy
```

Ručně ověřit:
- `DEBUG=False` (v `.env`)
- `SECRET_KEY` je nový, náhodný
- `ALLOWED_HOSTS` obsahuje API doménu
- `CORS_ALLOWED_ORIGINS` / `CSRF_TRUSTED_ORIGINS` obsahují domény salonů
- HTTPS funguje, `http://` se přesměruje na `https://`
- oprávnění pro logy/média: fotky jdou na Bunny (žádná lokální média);
  logy jdou na stdout (`docker compose logs`), volitelně `LOG_DIR`

## 6. Nasazení frontendů salonů

Logika aplikace se nemění — jen na jeden salon:
1. doména salonu → CNAME/A na Bunny Pull Zone (nebo nginx),
2. v `salonX/*.js` nastavit `API_BASE = 'https://api.vase-domena.cz/api'` a `SALON_ID`,
3. branding (CSS, loga, texty).

Statika salonů (HTML/CSS/JS) se nahrává na Bunny `webs/salon-{id}/`.

## 7. Cron úlohy

Běží ve službě `cron` (interval 1 h): připomínky, děkovné e-maily, GDPR anonymizace, mazání.
```bash
docker compose logs cron
docker compose exec api python manage.py rezervace_zivotni_cyklus   # ruční spuštění
```

### Test celého životního cyklu (na testovacích datech)

Cyklus se dá otestovat deterministicky pomocí simulovaného posunu času – není třeba
čekat hodiny/měsíce. Doporučeno na **testovacím** prostředí (příkaz mění data).

```bash
# 1) testovací data + rezervace v minulosti (viz seed / admin)
docker compose exec api python manage.py seed_salons
docker compose exec api python manage.py seed_rezervace

# 2) simulace jednotlivých fází (posun času vpřed):
docker compose exec api python manage.py rezervace_zivotni_cyklus --posun-hodin 3      # +3 h → děkovný e-mail
docker compose exec api python manage.py rezervace_zivotni_cyklus --posun-hodin 25     # +25 h → anonymizace
docker compose exec api python manage.py rezervace_zivotni_cyklus --posun-hodin 8784   # +12 měs. → soft-delete + úklid
```

Očekávaný tok: rezervace → dokončeno → +2 h děkovný e-mail → +24 h anonymizace → +12 měsíců smazání.
V produkci se `--posun-hodin` **nepoužívá** (cron běží s reálným časem).

## 8. Kompletní test produkce (před ostrým spuštěním)

1. Vytvoření rezervace (frontend salonu → API).
2. Potvrzovací e-mail dorazil.
3. Výzva k potvrzení / potvrzení termínu.
4. Storno přes odkaz v e-mailu.
5. Dokončení služby → děkovný e-mail (+2 h, přes cron).
6. Anonymizace po 24 h od konce služby (cron).
7. Úplné smazání po 12 měsících (retence, cron).
8. QR platba (SPAYD).
9. E-mailové notifikace (per-salon SMTP).
10. Health check: `curl https://api.vase-domena.cz/health/` → `{"status":"ok"}`.

Pro test časovaných kroků (5–7) použijte `--posun-hodin` (viz sekce 7).

## 9. Zálohování a obnova

Denní záloha přes cron na hostiteli:
```bash
crontab -e
# 0 3 * * * cd /opt/ulov && bash deploy/backup.sh >> /var/log/ulov-backup.log 2>&1
```
Zálohuje se PostgreSQL dump + `.env` + `docker-compose.yml` + Nginx/certbot konfigurace do `./backups`.

### Test OBNOVY (důležitější než samotná záloha — vyzkoušet aspoň jednou!)

Drill: **záloha → čistá DB → restore → ověření dat**. Skript `deploy/restore.sh` obnoví
zálohu do oddělené ověřovací databáze (ostrá data zůstanou nedotčená):
```bash
bash deploy/backup.sh                                  # vytvoř zálohu
bash deploy/restore.sh backups/db_YYYYMMDD_HHMMSS.sql.gz   # → DB "ulov_restore_test"
# skript vypíše počty salonů/rezervací = důkaz, že data jsou obnovitelná
```
Ostrá obnova při havárii: `bash deploy/restore.sh <záloha> ulov` (přepíše produkční DB).

## 10. Test výpadku (self-healing)

Všechny služby mají `restart: unless-stopped`, migrace běží při startu `api`. Ověřte, že po
restartu vše samo naběhne:
```bash
docker compose restart db           # restart PostgreSQL → api se znovu připojí
docker restart $(docker compose ps -q api)   # restart aplikace
sudo reboot                          # restart celého VPS → docker + compose nastartují samy
```
Po každém testu: `docker compose ps` (vše `Up`) a `curl .../health/` → `ok`.

> Pozn.: aby se stack po rebootu VPS spustil sám, musí být Docker povolený ve startu:
> `sudo systemctl enable docker`.

## 11. Load test (změřit čísla)

Read-only zátěž na veřejné endpointy (netvoří rezervace). Spouštět na **testovacím** prostředí:
```bash
pip install locust
locust -f deploy/loadtest/locustfile.py --host https://api.vase-domena.cz \
       --users 50 --spawn-rate 10 --run-time 2m --headless
# a poté --users 100
```
Souběžně na serveru měřte `docker stats` (CPU/RAM kontejnerů). Zaznamenejte odezvu API,
CPU a RAM pro 50 a 100 uživatelů.

## 12. Monitoring

- **Health endpoint** — `GET /health/` vrací `{"status":"ok","database":"ok"}` a kontroluje i DB
  (503 při výpadku databáze). Toto sledujte v Uptime Kuma (ne jen že běží Nginx).
- **Sentry** — nastavit `SENTRY_DSN` v `.env` (chyby aplikace). Bez DSN se nic neaktivuje.
- **Uptime Kuma** — monitor na `https://api.vase-domena.cz/health/` + domény salonů.
- **Disk** — `deploy/disk-check.sh` (varování při 80 %, kritické při 90 %) v cronu:
  ```bash
  # 0 * * * * cd /opt/ulov && bash deploy/disk-check.sh >> /var/log/ulov-disk.log 2>&1
  ```
  Hlídá plnění diskem (logy, zálohy, Docker image, certifikáty). Úklid: `docker system prune -af`.
- Zdroje/DB: `docker stats`, `docker compose exec db psql -U ulov -c "\l+"`.
- E-maily: chybovost v `docker compose logs api` (a Sentry).

## 13. Běžný provoz

```bash
docker compose ps                 # stav služeb
docker compose logs -f api        # logy API
docker compose pull && docker compose up -d --build   # aktualizace
docker compose exec api python manage.py migrate      # po nových migracích
```

---

*Architektura zůstává multi-tenant (jedna DB, izolace přes `salon_id`). Tento runbook mění pouze
provozní vrstvu (PostgreSQL, HTTPS, kontejnery, zálohy, monitoring), nikoli logiku aplikace.*
