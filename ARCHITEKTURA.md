# ULOV KLIENTY — architektura a provoz (stručně)

**Produkt:** web na míru + online rezervace pro salony, provozovny, řemesla a zdraví  
**Repo:** `Hakliano/Ulov_Rezervace`  
**Verze:** červenec 2026

Detailnější technické materiály: `TECHNICKE_NASAZENI.md`, `NASAZENI_PRODUKCE.md`, `deploy/DEPLOY_PIPELINE.md`.

---

## 1. Co systém dělá

| Vrstva | Funkce |
|--------|--------|
| **Prezentační web** (`presentace/`) | Marketing hub, vertikály (beauty, zdraví, řemesla, provozovny), poptávkový formulář |
| **Web klienta** (`salonN/`, vertikální dema) | Veřejný web — úvod, galerie, personál, ceník, novinky, kontakt |
| **Rezervace** (`rezervace.html` + JS) | Výběr služby, personálu, termínu; potvrzení e-mailem; storno tokenem |
| **Administrace** (v rezervačním UI) | Obsah webu, kalendář, personál, nastavení, NO-show, QR platby, statistiky |
| **Backend API** (`backend/`) | Multi-tenant logika, e-maily, uploady, GDPR životní cyklus rezervací |

Jeden backend obsluhuje **více salonů** (tenantů). Data jsou izolovaná přes `salon_id`.

---

## 2. Architektura (přehled)

```
┌─────────────────────────────────────────────────────────────────┐
│  Prohlížeč                                                      │
│  presentace/  salon1–8/  zdravi-*/ remesla-*/ provoz-*/         │
│  (HTML + CSS + vanilla JS, SALON_ID v app.js / rezervace.js)    │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTPS REST  →  api.ulovklienty.cz
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  Hetzner VPS — Docker Compose                                   │
│  nginx (TLS, statika) → Gunicorn → Django 5 + DRF              │
│  PostgreSQL 16 │ Redis 7 │ Celery worker │ cron (životní cyklus)│
└──────┬──────────────────┬──────────────────┬────────────────────┘
       │                  │                  │
       ▼                  ▼                  ▼
  PostgreSQL          Bunny.net CDN       SMTP per salon
  (ulov / ulov_staging)  (obrázky)         (e-maily)
```

**Staging** běží na stejném serveru jako LIVE — oddělená DB (`ulov_staging`), statika v `www-staging/`, API kontejner `ulov-staging-api`.

---

## 3. Technologie

| Oblast | Stack |
|--------|--------|
| Frontend | Statické HTML/CSS/JS (bez frameworku), responzivní layout |
| API | Django 5, Django REST Framework, CORS |
| DB | PostgreSQL 16 (produkce/staging), SQLite jen lokální dev |
| Fronta | Redis 7 + Celery (odesílání e-mailů) |
| Web server | Nginx + Let's Encrypt (Certbot) |
| Kontejnery | Docker Compose (`docker-compose.yml`, `docker-compose.staging.yml`) |
| Média | Bunny.net Storage + CDN (`webs/salon-{id}/…`) |
| E-maily | SMTP nastavení per salon; staging má `EMAIL_OVERRIDE_TO` |
| Platby | QR kódy SPAYD (české banky) |

---

## 4. Struktura repozitáře

| Složka | Účel |
|--------|------|
| `backend/` | Django API — aplikace `salons`, `rezervace`, `partner_admin` |
| `salon1/` … `salon8/` | Beauty dema (web + rezervace + admin) |
| `zdravi-*`, `remesla-*`, `provoz-*` | Vertikální dema (fyzio, veterina, instalatér, autoservis…) |
| `presentace/` | Hub + landingy vertikál + marketingové stránky |
| `shared/` | Sdílené assety (např. patička tvůrce) |
| `deploy/` | Deploy skripty, nginx, zálohy, runbooky |
| `www/` | **Výstup na serveru** — sync z gitu při deployi (není zdroj pravdy) |

**Zdroj pravdy pro weby je git.** Složka `www/` na Hetzneru je jen nasazená kopie.

---

## 5. Napojení a URL

### LIVE

| Služba | URL |
|--------|-----|
| Hub / presentace | https://www.ulovklienty.cz/ |
| Vertikály | `/beauty/`, `/zdravi/`, `/remesla/`, `/provozovny/` |
| Vertikální dema | `/zdravi-fyzio/`, `/provoz-pujcovna/`, … |
| Beauty dema | `demo1.ulovklienty.cz` … `demo8.ulovklienty.cz` → `salon1` … `salon8` |
| API | https://api.ulovklienty.cz/api/ |
| Health | https://api.ulovklienty.cz/health/ |

### Staging

| Služba | URL |
|--------|-----|
| Hub | https://www.staging.ulovklienty.cz/ |
| Dema | https://www.staging.ulovklienty.cz/salon1/ … |
| API | https://api-staging.ulovklienty.cz/ |

### Externí služby

- **GitHub** — verzování, větve `dev` / `main`
- **Bunny.net** — CDN pro loga, hero, galerie, upload z administrace
- **SMTP** — odesílání z rezervací (připomínky, potvrzení, recenze)
- **DNS** — `*.ulovklienty.cz` → Hetzner `49.13.23.65`

### API konvence

- Base: `/api/salon/<id>/…`
- Veřejné: čtení webu, volné termíny, vytvoření rezervace
- Admin zápis: hlavička `X-Admin-Password`
- Poptávka z presentace: `POST /api/poptavka/`

---

## 6. Hlavní funkce backendu

**`salons`** — obsah webu  
Ceník, novinky, galerie, personál na webu, otevírací doba, upload obrázků na Bunny.

**`rezervace`** — booking engine  
Kalendář, zaměstnanci a rozvrhy, rezervace, storno, zákaznické účty, NO-show archiv, QR platby, statistiky.

**`partner_admin`** — nastavení partnerů (domény, upozornění).

**Cron / Celery** — životní cyklus  
Připomínky, děkovné e-maily s výzvou k recenzi, anonymizace a mazání dle GDPR.

---

## 7. Multi-tenant model

- Jedna databáze, více salonů (`Salon` + `salon_id` u všech dat).
- Každý salon: vlastní branding, SMTP, admin heslo, Bunny prefix.
- Zákaznická data a NO-show **se mezi salony nesdílí**.
- Frontend má pevně `SALON_ID` v `app.js` / `rezervace.js` (např. `demo3` → salon 3).

---

## 8. Deploy pipeline

```
LOCAL (Cursor) → GitHub DEV → Staging → (schválení) → GitHub MAIN → LIVE
```

| Krok | Akce | Kdo |
|------|------|-----|
| ① | Commit + `git push origin dev` | Po lokální kontrole |
| ② | `bash deploy/deploy-staging.sh origin/dev` | Na Hetzneru |
| — | Test na staging URL | Ty |
| ③ | `git push origin dev:main` | Po schválení stagingu |
| ④ | `bash deploy/deploy-live.sh origin/main` | Jen po výslovném „na LIVE“ |

**Pravidla:**
- Staging **jen z `dev`**, LIVE **jen z `main`**.
- Žádný přímý `scp`/`rsync` z PC do `www/`.
- Před LIVE: záloha (`deploy/backup.sh`), checklist (`deploy/pre-deploy-check.sh`).
- Havárie: `deploy/rollback-live.sh`.

Cursor rule: `.cursor/rules/deploy-safety.mdc`.

---

## 9. Běžné použití (vývojář)

### Lokální práce

```bash
git checkout dev
git pull origin dev
# úpravy v salonN/, presentace/, backend/
git add …
git commit -m "…"
git push origin dev
```

### Staging

```bash
ssh root@49.13.23.65
cd /opt/ulov
bash deploy/deploy-staging.sh origin/dev
```

### LIVE (po schválení)

```bash
git push origin dev:main
ssh root@49.13.23.65 'cd /opt/ulov && bash deploy/deploy-live.sh origin/main'
```

Po deployi API občas nginx vrátí 502 → `docker compose exec -T nginx nginx -s reload`.

### MacBook na cestách

Návod pro Cursor agenta: `deploy/MACBOOK_CURSOR_SETUP.md`.

---

## 10. Provoz na serveru

| Cesta / služba | Popis |
|----------------|--------|
| `/opt/ulov` | LIVE aplikace + git checkout |
| `docker compose` | `db`, `api`, `worker`, `cron`, `nginx`, `certbot` |
| `www/` | Nasazená statika (salony, presentace, dema) |
| `www-staging/` | Staging statika |
| `backups/` | DB + config + www zálohy (14 dní retence) |

Seed dem: `python manage.py seed_vertical_demos` (staging po obnově DB).

---

## 11. Související dokumentace

| Dokument | Obsah |
|----------|--------|
| `PREHLED_PRO_SALES_A_MARKETING.md` | Produkt, výhody, funkce pro obchod |
| `For Compliance v1.md` | Funkce + GDPR podklad pro právní / DPA / ROPA |
| `PODKLAD_PRO_PARTNERY.md` | Ceník, balíčky, služby, kompletní FLOW pro partnerské smlouvy |
| `TECHNICKE_NASAZENI.md` | API, datový model, hardening |
| `NASAZENI_PRODUKCE.md` | Runbook prvního nasazení |
| `deploy/DEPLOY_PIPELINE.md` | Staging, rollback, FAQ |
| `deploy/DEPLOY_SAFETY.md` | Bezpečný sync, incidenty |
| `deploy/MACBOOK_CURSOR_SETUP.md` | Setup MacBooku pro vývoj |
| `deploy/runbook-email-fronta.md` | Celery, Redis, e-mailová fronta |
| `deploy/TESTOVACI_PRISTUPY.md` | Loginy majitelů dem (web + FLOW) |
