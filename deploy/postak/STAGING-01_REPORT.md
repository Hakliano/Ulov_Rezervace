# STAGING-01 — Pošťák (stav k dokončení nasazení)

## Navrhovaná STAGING URL (ke schválení)

| Varianta | URL | Poznámka |
|----------|-----|----------|
| **Doporučeno** | `https://www.staging.ulovklienty.cz/postak/` | Stejný path jako budoucí LIVE (`/postak/`), existující cert/DNS staging hubu, **bez** dotyku LIVE `/postak/`. |
| Alternativa | `https://postak.staging.ulovklienty.cz/` | Vyžaduje DNS + rozšíření cert SAN; `FORCE_SCRIPT_NAME` prázdný. |

**Nepoužívat:** přesměrování z `https://www.ulovklienty.cz/postak/` na staging.

---

## Přednasazení (lokálně provedeno)

| Kontrola | Výsledek |
|----------|----------|
| Testy `jadro` | **107/107 OK** (LOCAL) |
| Přihlášení + vynucená změna hesla | implementováno (middleware + USER-02) |
| Odeslání přihlašovacích údajů | `send_system_message`, audit bez hesla |
| Logo v e-mailu | PNG `postak-logo-email.png`, ne WebP v mailu |
| Bunny integrace | kód + `postak_bunny_smoke`; prefix staging = `postak/staging/` |
| Django produkce | `DEBUG=False` vyžaduje `SECRET_KEY`, `POSTAK_MAIL_ENCRYPTION_KEY`; secure cookies |

---

## P0 — blokery před skutečným nasazením

1. **Git / GitHub DEV** — většina Pošťáka (a `backend/partner_admin/postak_api.py` pro Moderník CRM) je **necommitnutá** / nepushed. Server deployuje z `origin/dev` → bez commit + push **nelze** nasadit konzistentní verzi.
2. **SSH na Hetzner** — z tohoto prostředí **není** ověřený přístup (`Host key verification failed`). Nasazení musí provést operátor se serverovým SSH.
3. **Nginx snippet** — `deploy/postak/nginx-staging-snippet.conf` musí být ručně vložen do `staging.conf` a nginx reload **bez** změny LIVE vhostů.

---

## P1 — před plnou funkčností na stagingu

1. **Moderník Postak API** na `api-staging` — endpointy v repu u partner_admin **nejsou** na DEV v gitu; bez deploye backendu staging CRM sync nefunguje.
2. **HYA API** — ověřit staging URL/token; jinak klienti HYA pouze z cache/mock.
3. **DELETE klientů** — UI Pošťáka **nemá** mazání do Moderníku; funkce `smazat()` v `modernik_client` existuje, API staging/LIVE umí DELETE — **před LIVE** zúžit oprávnění na serveru Moderníku (známý problém).
4. **E-mailové testy** — jen schválené testovací schránky; nastavit `POSTAK_SYSTEM_SCHRANKA_ID` na staging DB.

---

## P2

- Upload `postak-logo-email.png` na veřejnou URL staging (static po deployi).
- Zúžení přístupu ke staging (VPN / HTTP auth na `/postak/`) — zatím jen Django login.
- Dokumentace záloh Bunny (`postak_bunny_backup`) do cronu na serveru.

---

## Připravená infrastruktura (v repu)

- `postak/docker-compose.staging.yml` — Postgres + Gunicorn, volumes `postak_staging_*`, síť `ulov_default`.
- `postak/.env.staging.example` — Bunny `postak/staging/`, staging API URL.
- `postak/postak_site/settings.py` — PostgreSQL přes `POSTGRES_HOST`.
- `deploy/postak/deploy-staging-postak.sh` — build, migrate, bunny smoke, curl check.
- `deploy/postak/nginx-staging-snippet.conf` — reverse proxy `/postak/`.

### Bunny

- Zone: `wwweb`
- Staging prefix: **`postak/staging/`** (env `POSTAK_BUNNY_ROOT_PREFIX`)
- LIVE (až později): `postak/`
- Smoke: `python manage.py postak_bunny_smoke` — test pouze pod prefixem z env.

### CRM (staging)

- Moderník: `MODERNIK_API_BASE=https://api-staging.ulovklienty.cz/partner-admin/api/postak/v1`
- Token: staging-only secret (ne LIVE).
- Zápis do ostrých DB Moderníku/HYA **zakázán** — používat výhradně staging API.

### Zálohy / rollback

- DB: `docker compose -p postak-staging ... run --profile backup backup`
- Rollback: `docker compose ... down` + obnovit dump; Bunny nezávisle přes `postak_bunny_backup`.
- Odstranění Pošťáka: `docker compose -p postak-staging down -v` (neovlivní `ulov-staging`).

---

## Funkční testy po nasazení (checklist)

Provést ručně na schválené STAGING URL po P0 vyřešení:

1. Přihlášení / odhlášení, SUPERUSER vs USER  
2. Přehled, Nápověda  
3. E-mail (čtení, odeslání, koncepty) — testovací schránky  
4. Chat, klienti M/HYA, kalendář, poznámky  
5. Dokumentace + Bunny upload/download/delete  
6. Správa uživatelů, uvítací e-mail  
7. Mobilní zobrazení  

---

## Ostatní projekty

Samostatný compose `postak-staging`, vlastní Postgres volume — **nesdílí** DB ani media s Moderníkem/HYA/Materiálníkem. Nginx snippet jen ve **staging** server block.

---

## Co zbývá před LIVE

- Schválení staging URL a kompletní checklist testů na internetu.
- Commit + push celého Pošťáka + Postak API na DEV → staging deploy.
- Nasazení nginx snippet + reload staging.
- Bunny prefix přepnout na `postak/` (ne `staging/`) až po schválení.
- LIVE deploy **jen z MAIN** po tvém explicitním souhlasu — **neprovádět automaticky**.

---

## Commit / verze pro staging deploy

| Commit | Popis |
|--------|--------|
| `86f8d73` | Pošťák — kostra (auth, role) |
| `ce2b0b9` | Plná aplikace + Postak API + staging deploy artefakty |

`origin/dev` po pushi směřuje na **`ce2b0b9`**. NASAZENÍ NA SERVER ZATÍM **NESPUŠTĚNO**.

*Po deployi doplnit:* výstup `git rev-parse HEAD` na serveru po `deploy-staging-postak.sh`.
