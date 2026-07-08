# Ulov Rezervaci — technický popis a nasazení (pro developery)

**Verze:** červenec 2026  
**Cílové měřítko:** desítky salonů na jeden backend (multi-tenant)  
**Stav kódu:** funkční MVP / lokální vývoj — před produkcí vyžaduje hardening (viz sekce 8)

---

## 1. Přehled architektury

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Klient (prohlížeč)                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                 │
│  │ salon1/      │  │ salon2/      │  │ salonN/      │  statické weby  │
│  │ index.html   │  │ index.html   │  │ …            │  + rezervace.html│
│  │ app.js       │  │ app.js       │  │              │  + rezervace.js  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘                 │
│         │ SALON_ID=1      │ SALON_ID=2      │                           │
└─────────┼─────────────────┼─────────────────┼───────────────────────────┘
          │                 │                 │
          └────────────────┬┴─────────────────┘
                           │ HTTPS JSON (REST)
                           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Django 5 + Django REST Framework (backend/)                            │
│  ├── salons/     webový obsah, upload obrázků, Bunny.net              │
│  └── rezervace/  booking engine, e-maily, NO-show, QR platby           │
└─────────┬───────────────────────┬───────────────────────┬─────────────┘
          │                       │                       │
          ▼                       ▼                       ▼
   ┌─────────────┐        ┌─────────────┐        ┌─────────────┐
   │ PostgreSQL  │        │ Bunny.net   │        │ SMTP salonů │
   │ (doporuč.)  │        │ Storage+CDN │        │ per salon   │
   └─────────────┘        └─────────────┘        └─────────────┘
          ▲
          │ cron každou hodinu
   ┌──────┴──────────────────┐
   │ rezervace_zivotni_cyklus │
   │ (e-maily → anonymizace   │
   │  → smazání)              │
   └──────────────────────────┘
```

**Multi-tenant model:** jedna sdílená databáze, izolace dat přes `salon_id` (ForeignKey na `Salon`). Salony **nesdílejí** zákaznická data ani NO-show archiv mezi sebou (GDPR).

---

## 2. Repozitář a komponenty

| Složka | Role | Technologie |
|--------|------|-------------|
| `backend/` | API, business logika, e-maily, cron | Django 5, DRF, `qrcode` |
| `salon1/`, `salon2/` | Statický frontend jednoho salonu | HTML, CSS, vanilla JS |
| `backend/db.sqlite3` | Dev databáze | SQLite (není pro produkci) |
| `backend/.env` | Secrets (Bunny, SMTP, heslo admina) | env soubor |

### Django aplikace

**`salons`** — veřejný web salonu  
- Model `Salon`, `CenikPolozka`, `Novinka`, `SalonObrazek`, `OteviraciDoba`  
- API: `GET/PUT /api/salon/<id>/`, upload obrázků, Bunny status  

**`rezervace`** — rezervační systém  
- Modely: `Rezervace`, `Zakaznik`, `Zamestnanec`, `RezervacniNastaveni`, `NoShowZaznam`, …  
- Veřejné endpointy (bez hesla): info, volné termíny, vytvoření rezervace, storno tokenem, registrace zákazníka  
- Admin endpointy: kalendář, personál, nastavení, NO-show, platba QR, statistiky  

---

## 3. API — konvence

**Base URL:** `https://api.vasedomena.cz/api/` (v dev: `http://localhost:8000/api/`)

**Tenant routing:** všechny cesty obsahují `salon/<int:pk>/` — `pk` je primární klíč v tabulce `Salon`.

### Veřejné endpointy (bez autentizace)

| Metoda | Cesta | Účel |
|--------|-------|------|
| GET | `/salon/<id>/` | Data webu (texty, ceník, galerie) |
| GET | `/salon/<id>/personel/` | Personál pro web |
| GET | `/salon/<id>/rezervace/info/` | Služby, zaměstnanci, nastavení |
| GET | `/salon/<id>/rezervace/volne-terminy/` | Generování slotů |
| POST | `/salon/<id>/rezervace/` | Nová rezervace |
| POST | `/salon/<id>/rezervace/storno/<uuid>/` | Storno |
| GET | `/salon/<id>/rezervace/<id>/ics/` | Kalendářový soubor |
| POST | `/salon/<id>/rezervace/zakaznik/registrace/` | Účet zákazníka |
| POST | `/salon/<id>/rezervace/zakaznik/prihlaseni/` | Přihlášení |
| GET | `/salon/<id>/rezervace/zakaznik/moje/?token=` | Moje rezervace |

### Admin endpointy

Zápis vyžaduje HTTP hlavičku:

```http
X-Admin-Password: <heslo>
```

Některé admin čtení (web PUT, rezervační admin GET) je veřejné; zápis vždy chráněný (`AdminPasswordPermission` / `MajitelPermission`).

Kompletní seznam: `backend/rezervace/urls.py`, `backend/salons/urls.py`.

### Frontend konfigurace

Každý statický frontend má na začátku `rezervace.js` / `app.js`:

```javascript
const API_BASE = 'https://api.vasedomena.cz/api';
const SALON_ID = 42;  // pevně zakódované pro daný deploy
```

Pro desítky salonů je potřeba **build krok** nebo **konfigurační soubor** (viz sekce 6).

---

## 4. Datový model (zjednodušeně)

```
Salon (1) ──┬── CenikPolozka (N)     služby / ceník
            ├── Zamestnanec (N)      personál + rozvrh + absence
            ├── Rezervace (N)        booking
            ├── Zakaznik (N)         účty per salon (stejný e-mail = jiný záznam v jiném salonu)
            ├── RezervacniNastaveni (1)  intervaly, notifikace JSON, SMTP
            ├── NoShowZaznam (N)     archiv NO-show per salon
            └── Novinky, Obrázky, …

Rezervace ──┬── RezervaceSluzba (N)
            ├── Zakaznik (nullable)
            └── cancel_token (UUID) pro storno bez přihlášení
```

**Důležité JSON pole:** `RezervacniNastaveni.notifikace` — pole až 4 notifikací (časované +2 ruční), normalizováno přes `notifikace_defaults.py`.

**Časová zóna:** `Europe/Prague`, `USE_TZ = True` — všechny `DateTimeField` v UTC v DB, zobrazení v lokálním čase.

---

## 5. Klíčové business služby (backend)

| Modul | Soubor | Odpovědnost |
|-------|--------|-------------|
| Volné termíny | `services/availability.py` | Sloty, kolize, svátky, absence, blokace |
| Otevírací doba | `services/oteviraci_doba.py` | Sjednocení rozvrhů zaměstnanců |
| E-maily | `services/emails.py`, `notifikace_email.py` | SMTP per salon, HTML + přílohy |
| QR platba | `services/platba_qr.py` | SPAYD, PNG QR |
| Životní cyklus | `services/zivotni_cyklus.py` | E-maily, anonymizace, mazání — jeden cron |
| GDPR / anonymizace | `services/gdpr.py` | Hash e-mailů, výmaz osobních údajů |
| NO-show reputace | `services/email_reputace.py` | Počítadla a blokace **jen v salonu** |

Podrobný diagram životního cyklu: **[ZIVOTNI_CYKLUS_REZERVACE.md](ZIVOTNI_CYKLUS_REZERVACE.md)**

### Cron (povinný v produkci)

```bash
# každou hodinu — jediný příkaz pro celý životní cyklus dat
python manage.py rezervace_zivotni_cyklus
```

Alias (zpětná kompatibilita): `odesli_pripominky`, `gdpr_udrzba`.

Kroky v jednom běhu:
1. Připomínky (+24 h před termínem) a děkovný e-mail (+2 h po službě) → `thank_you_sent_at`
2. Anonymizace po 24 h od konce služby → `anonymized_at`
3. Soft-delete po 12 měsících → `deleted_at`
4. Fyzické smazání starých záznamů a úklid audit logu

---

## 6. Nasazení desítek salonů — strategie frontendu

**Současný stav:** každý salon = kopie složky `salon1/` s jiným `SALON_ID`, CSS a brandem. Pro 2 salony OK, pro 50 neudržitelné.

### Doporučené varianty (seřazeno)

#### A) Šablona + build pipeline (nejblíž současnému stavu)

1. `frontend-template/` se zástupnými `{{SALON_ID}}`, `{{API_BASE}}`, `{{BRAND_CSS}}`
2. CI (GitHub Actions) pro každý salon: build → upload na Bunny `webs/salon-{id}/`
3. Vlastní doména salonu → CNAME na Bunny Pull Zone nebo reverse proxy

**Výhody:** plná designová volnost per salon  
**Nevýhody:** N deployů při změně `rezervace.js`

#### B) Jeden sdílený frontend + konfigurace z API (doporučeno střednědobě)

1. Jedna aplikace na `rezervace.ulovrezervaci.cz`
2. `SALON_ID` nebo `slug` z URL: `?salon=studio-krasa` nebo subdoména `krasa.ulov.cz`
3. API rozšířit o `GET /api/salon/by-slug/<slug>/` a `theme` JSON (barvy, fonty)
4. CSS variables načtené z konfigurace

**Výhody:** jeden deploy JS, rychlé opravy  
**Nevýhody:** nutný refaktor frontendu, omezenější unikátní layouty

#### C) Hybrid (praktický kompromis)

- Sdílený `rezervace.js` z CDN (verzovaný `?v=…`)
- Per salon jen `config.js` + `brand.css` + `index.html` kostra
- Webové stránky zůstanou custom, rezervace sdílená

---

## 7. Doporučené produkční nasazení (názor autora)

Pro **desítky salonů na jednom backendu** v ČR/EU:

### Fáze 1 — MVP produkce (1–20 salonů)

| Komponenta | Doporučení | Proč |
|------------|------------|------|
| **VPS** | [Hetzner](https://www.hetzner.com) CX32 nebo CPX31 (4 vCPU, 8 GB RAM) | Cena/výkon, EU datacentra (Falkenstein/Nuremberg), nízká latence z CZ |
| **OS** | Ubuntu 24.04 LTS | |
| **App server** | Gunicorn + Nginx | Osvědčený stack pro Django |
| **Databáze** | PostgreSQL 16 na stejném VPS (nebo Hetzner Managed DB) | SQLite **nesmí** do produkce při více salonech |
| **Static + obrázky** | Bunny.net (už v projektu) | CDN, levné úložiště, `webs/salon-{id}/` |
| **TLS** | Let's Encrypt (Certbot) | |
| **Cron** | systemd timer na VPS | `rezervace_zivotni_cyklus` |
| **Procesy** | Docker Compose (volitelně, ale doporučeno) | reprodukovatelné deploye |

**Odhad nákladů:** řádově 15–40 €/měsíc infra + Bunny dle trafficu.

### Fáze 2 — růst (20–80 salonů)

| Komponenta | Upgrade |
|------------|---------|
| DB | Managed PostgreSQL (zálohy, PITR) |
| App | 2× app instance za load balancerem |
| E-maily | fronta (Celery + Redis) místo synchronního SMTP v requestu |
| Cache | Redis pro `volne-terminy` (nejtěžší endpoint) |
| Monitoring | Sentry (chyby), Uptime Kuma / Better Stack |

### Fáze 3 — pokud přesáhnete jeden VPS

- Kubernetes (Hetzner k3s) **až když** máte provozní důvod — pro desítky salonů často zbytečně brzy
- Alternativa: [Fly.io](https://fly.io) nebo [Railway](https://railway.app) pro menší tým bez DevOps

### Kde **nenasazovat** jako první volbu

- **SQLite na produkci** — zámky při concurrent zápisech rezervací
- **Jeden sdílený admin password** pro všechny salony — bezpečnostní riziko (viz 8.1)
- **CORS `ALLOW_ALL_ORIGINS`** — v produkci whitelist domén salonů

---

## 8. Checklist před spuštěním produkce

### 8.1 Bezpečnost (kritické)

| Položka | Současný stav | Cíl |
|---------|---------------|-----|
| `SECRET_KEY` | Hardcoded v `settings.py` | Env proměnná, rotovat |
| `DEBUG` | `True` | `False` |
| `ALLOWED_HOSTS` | localhost only | API doména |
| Admin heslo | Jedno `SALON_ADMIN_PASSWORD` pro všechny | **Per-salon token** nebo JWT + role |
| CORS | `CORS_ALLOW_ALL_ORIGINS = True` | Whitelist `https://*.salon-domena.cz` |
| HTTPS | Ne | Povinné, HSTS |
| Rate limiting | Ne | DRF throttling na POST rezervace / login |
| SMTP hesla | V DB plaintext | Šifrování at rest nebo secrets manager |

### 8.2 Databáze

```python
# settings.py — produkce
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ['DB_NAME'],
        'USER': os.environ['DB_USER'],
        'PASSWORD': os.environ['DB_PASSWORD'],
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '5432'),
        'CONN_MAX_AGE': 60,
    }
}
```

Indexy k doplnění při růstu:
- `Rezervace(salon_id, zacatek)`
- `Rezervace(salon_id, stav)`
- `NoShowZaznam(salon_id, email)`
- `Zakaznik(salon_id, email)`

### 8.3 E-mail

Priorita odesílatele (implementováno v `get_email_config`):

1. SMTP z `RezervacniNastaveni` v DB (admin webu)
2. Env `SALON_{id}_SMTP_*`
3. Globální `EMAIL_*` z settings

Každý salon by měl mít **vlastní schránku** (Forpsi, Seznam Profi, Google Workspace).

### 8.4 Zálohy

- PostgreSQL: denní dump + WAL (managed DB to řeší)
- Bunny: verze souborů / pravidelné exporty kritických složek
- Media mimo DB: obrázky jsou na Bunny, ne v DB

---

## 9. Ukázkový Docker Compose (produkce)

```yaml
# docker-compose.yml — orientační kostra
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: ulov
      POSTGRES_USER: ulov
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data

  api:
    build: ./backend
    command: gunicorn salon_api.wsgi:application -b 0.0.0.0:8000 -w 4
    env_file: .env
    depends_on: [db]
    ports:
      - "8000:8000"

  cron:
    build: ./backend
    command: >
      sh -c "while true; do python manage.py rezervace_zivotni_cyklus; sleep 3600; done"
    env_file: .env
    depends_on: [db]

volumes:
  pgdata:
```

Nginx před `api` terminuje TLS a servíruje případně statiku.

---

## 10. Tok dat — typické scénáře

### 10.1 Online rezervace

```
Zákazník → rezervace.js
  → GET /rezervace/info/
  → GET /rezervace/volne-terminy/?datum&sluzby&zamestnanec
  → POST /rezervace/  { sluzby, datum, cas, email, … }
Backend:
  → vytvor_rezervaci() — kontrola blokace, kolizí
  → email_potvrzeni()
  → Response + cancel_token
```

### 10.2 Admin — NO-show

```
Personál → POST /admin/<rez_id>/no-show/
  → NoShowZaznam, aktualizuj_po_noshow()
  → volitelně e-mail (notifikace 3)
  → při 3× v salonu auto-blokace Zakaznik.blokovan
```

### 10.3 Upload obrázku webu

```
Admin web → POST /salon/<id>/upload/  (multipart)
  → salons/bunny.py → Bunny Storage
  → URL na CDN → uložení do Salon.hero_image nebo SalonObrazek
```

---

## 11. Škálování — co vydrží jeden backend

**Desítky salonů** s typickým provozem (řádově stovky rezervací/den celkem) — **jeden dobře nastavený VPS + PostgreSQL stačí**.

Úzká místa při růstu:

| Bottleneck | Příznak | Řešení |
|------------|---------|--------|
| `volne-terminy` | Pomalé načítání kalendáře | Cache (Redis), optimalizace dotazů |
| Synchronní SMTP | Timeout API při odeslání e-mailu | Celery task queue |
| Cron v jednom procesu | Zpožděné připomínky | Dedikovaný worker, monitoring |
| SQLite | `database is locked` | PostgreSQL |
| Obrázky | Velký upload | Přímo na Bunny (presigned URL — budoucí vylepšení) |

Odhad: **50–100 salonů** na jednom 4-vCPU serveru je reálný cíl po PostgreSQL + základní optimalizaci. Nad to už řešit horizontální škálování app serverů.

---

## 12. Nový salon — provozní postup

1. **DB:** `INSERT` do `Salon` (nebo admin / management command `seed_salons` rozšířit)
2. **Seed:** `python manage.py seed_rezervace` — nastavení, zaměstnanci (pokud prázdné)
3. **Frontend:** deploy statiky s `SALON_ID=N` na Bunny `webs/salon-N/`
4. **DNS:** doména salonu → CDN / nginx
5. **SMTP:** vyplnit v admin webu nebo env `SALON_N_SMTP_*`
6. **Cron:** běží globálně pro všechny salony
7. **Test:** rezervace, e-mail, storno, NO-show, QR platba

**Budoucí zlepšení:** `Salon.slug`, `Salon.custom_domain`, onboarding API.

---

## 13. Lokální vývoj

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env   # Bunny, SMTP
python manage.py migrate
python manage.py seed_salons
python manage.py seed_rezervace
python manage.py runserver

# terminál 2
cd salon1 && python -m http.server 5500

# terminál 3 (volitelně)
cd salon2 && python -m http.server 5501
```

- API: http://localhost:8000/api/  
- Salon 1: http://localhost:5500/rezervace.html  
- Admin heslo (dev): `admin123` (`SALON_ADMIN_PASSWORD`)

---

## 14. Shrnutí doporučení

| Oblast | Doporučení |
|--------|------------|
| **Hosting API** | Hetzner VPS + Docker + Nginx + Gunicorn |
| **DB** | PostgreSQL (managed nebo na VPS) |
| **CDN / statika / fotky** | Bunny.net (již integrováno) |
| **Frontend 50+ salonů** | Sdílený `rezervace.js` + per-salon `config.js` / build pipeline |
| **E-maily** | SMTP per salon; později Celery fronta |
| **Cron** | systemd nebo sidecar container |
| **Auth** | Před produkcí nahradit globální heslo per-salon tokeny |
| **Monitoring** | Sentry + uptime + logy Gunicorn |

Systém je architektonicky připraven na multi-tenant (`salon_id` všude), ale **provozní vrstva** (PostgreSQL, secrets, per-tenant auth, CORS, build frontendu) je potřeba doplnit před ostrým spuštěním pro desítky klientů.

---

*Dokument pro interní použití vývojového týmu. Při změně architektury aktualizujte sekce 6, 7 a 8.*
