# Pipeline: GitHub → staging → LIVE (+ rollback)

## Kanónický setup (zdroj pravdy)

```
LOCAL (Cursor)
   │ ① push
   ▼
GitHub DEV  ──────────────────────────────┐
   │ ② deploy                              │ ③ merge (až staging OK)
   ▼                                       ▼
Hetzner Staging                      GitHub MAIN
www.staging.ulovklienty.cz                 │ ④ deploy (až ty potvrdíš)
Copy DTB                                   ▼
                                   Hetzner LIVE
                                   www.ulovklienty.cz
                                   DTB (ostrá)
```

| Krok | Odkud | Kam | Kdo / kdy |
|------|-------|-----|-----------|
| ① | Cursor lokál | GitHub **DEV** | Po tvém „lokál OK“ — commit + push |
| ② | GitHub **DEV** | Hetzner **Staging** | Hned po ① — `deploy-staging.sh` z DEV |
| — | Ty testuješ | staging URL | Manuálně online |
| ③ | GitHub **DEV** | GitHub **MAIN** | Až staging schválíš |
| ④ | GitHub **MAIN** | Hetzner **LIVE** | Až výslovně řekneš „na LIVE“ |

**Pravidla:**
- Staging **jen z DEV**, LIVE **jen z MAIN** — nikdy naopak.
- Staging = **kopie DB** (Copy DTB). LIVE = **ostrá DTB**.
- Nic na Hetzner mimo GitHub (žádný přímý upload z PC).

**Dvě pojistky:** (1) staging před veřejností, (2) rollback LIVE na poslední dobrý tag/zálohu.

---

## Potvrzený provozní flow

```
1) Lokál OK (ty)
2) Push na GitHub DEV (agent)           ← ①
3) Deploy DEV → Staging (agent)         ← ②
4) Ty otestuješ www.staging.ulovklienty.cz
5) Ty schválíš → merge DEV → MAIN       ← ③
6) Ty řekneš „na LIVE“ → deploy MAIN    ← ④
```

Agent **nesmí** udělat ③/④ bez tvého potvrzení.

---

## Železné pravidlo

```
Lokál → GitHub DEV → Staging → (schválení) → MAIN → LIVE
```

**Zakázáno:**
- nahrát na LIVE soubory, které nejsou v GitHubu (`scp`/`rsync` z PC mimo git)
- měnit produkční `www/` nebo kód jen na serveru
- „rychlá oprava jen na Hetzneru“

**Povoleno na LIVE jen:**
- `git fetch` + checkout **konkrétního tagu / commitu z GitHubu**
- skripty v `deploy/` (záloha, sync z checkoutnutého stromu, rollback)

Cursor rule: `.cursor/rules/deploy-safety.mdc` + tento dokument.

---

## 1. Tvůj příklad (00:00 → 01:20 → 01:45)

```
00:00  LIVE běží OK
       → automaticky (nebo ručně) vznikne bod obnovy:
         tag  live-20260720-0000
         + backups/db_….sql.gz
         + backups/www_….tar.gz

01:20  Vymyslíme změnu (CSS / HTML / infra)
       → branch feature/…
       → commit + push na GitHub

01:30  Nasadíme branch na STAGING
       → test: web, rezervace, DB, e-mail (jen na testovací schránku)

01:45  Staging OK → merge do main → tag live-20260720-0145
       → záloha LIVE (nový bod)
       → deploy tagu na LIVE
       → smoke test

Když se LIVE rozbije:
       → rollback na tag live-20260720-0000 + DB/www z 00:00
```

---

## 2. Verze 1 — Staging (test před veřejností)

### Co staging musí umět

Stejný stack jako LIVE: nginx + statika + API + Postgres + Redis + Celery/worker + SMTP cesta.

Rozdíly od LIVE:

| Věc | Staging |
|-----|---------|
| URL | např. `staging.ulovklienty.cz`, `demo1.staging…` nebo port / druhý compose project |
| Kód | branch / PR z GitHubu (ne nutně `main`) |
| DB | **kopie** produkce (nebo anonymizovaný dump), oddělený volume |
| E-maily | SMTP na **test schránku** / Mailpit / stejný SMTP s `EMAIL_OVERRIDE_TO=tvuj@…` — **nikdy reálným zákazníkům** |
| Bunny / upload | testování OK; nemazat produkční média omylem (oddělený prefix nebo read-only) |

### Minimální varianta na stejném VPS (doporučení teď)

Jeden server, druhý Compose project:

```text
/opt/ulov          → LIVE   (compose project name: ulov)
/opt/ulov-staging  → STAGING (ulov-staging), vlastní .env + volumes
```

- DNS: `staging.ulovklienty.cz` + případně `api-staging.ulovklienty.cz`
- Deploy staging: `git fetch && git checkout <branch> && docker compose up -d --build` + sync `www/`
- Po schválení: merge do `main`, tag, deploy LIVE skriptem

### Co testovat na stagingu (smoke před LIVE)

- [ ] Hub + vertikály + dema načtou obsah (ne „nepodařilo načíst“)
- [ ] Rezervace: vytvořit → e-mail dorazí na **test** adresu
- [ ] Admin přihlášení dema
- [ ] Health: `/health/` ok, CORS z staging domény
- [ ] Po změně infra: migrace doběhly, worker běží
- [ ] `bash deploy/pre-deploy-check.sh` na všechny syncované složky

Dokud checklist není hotový → **na LIVE se nejde**.

---

## 3. Verze 2 — Bod obnovy „stav 00:00“

I se stagingem potřebuješ rollback: staging nechytí vše (DNS, cert, lidská chyba při promote).

### Co tvoří jeden „bod obnovy“

| Artefakt | Účel |
|----------|------|
| **Git tag** na GitHubu `live-YYYYMMDD-HHMM` | Přesný kód + statika ve stromu |
| **`db_….sql.gz`** | Stav databáze |
| **`www_….tar.gz`** | Nasazená statika (pojistka i kdyby git a www divergovaly) |
| **`config_….tar.gz`** | `.env` + nginx (bez commitování secretů do gitu) |

Vzniká:
- denně cronem (`deploy/backup.sh`)
- **vždy těsně před** každým LIVE deployem
- ideálně i v klidu „vše běží“ (ruční tag `live-known-good`)

### Rollback (cíl: minuty, ne hodiny)

1. `git fetch` → checkout tagu `live-…-0000`
2. Obnovit `www/` z `www_….tar.gz` (nebo sync z checkoutu)
3. Obnovit DB z `db_….sql.gz` (pozor: přijdeš o rezervace vzniklé po bodu — u dem OK, u platících komunikovat)
4. `docker compose up -d` + health check

Skript: `deploy/rollback-live.sh` (viz níže).  
**Nikdy** „rollback“ jen přepsáním pár souborů z PC.

---

## 4. GitHub jako jediná cesta na LIVE

### Model větví (kanón)

```
LOCAL → push → DEV  →  deploy Staging (Copy DTB)
                 │
                 └─ merge (po schválení stagingu) → MAIN → deploy LIVE (ostrá DTB)
```

- **DEV** = jediný zdroj pro Staging  
- **MAIN** = jediný zdroj pro LIVE  
- Feature větve volitelně; před stagingem vždy sjednotit do **DEV**

### Co musí být v gitu

- backend, compose, nginx šablony
- **kompletní** `salonN/`, `presentace/`, vertikální dema (`index.html` včetně)
- `deploy/*.sh`, runbooky

Co **nesmí** být jediný zdroj na LIVE: necommitnuté lokální HTML/CSS.

### Enforce (postupně)

1. **Teď (proces):** zákaz přímého uploadu — skripty + Cursor rule  
2. **Hned:** LIVE deploy jen `deploy/deploy-live.sh` (fetch z `origin`, tag)  
3. **Další krok:** GitHub Environment `production` + ruční approve; volitelně CI  
4. **Tvrdší:** na serveru odebrat zvyk „rsync z laptopu“; SSH jen pull/script

---

## 5. E-maily při testu

Bez ochrany staging/test spustí reálné maily zákazníkům.

Doporučení:
- staging `.env`: `EMAIL_OVERRIDE_TO=info@…` nebo Mailpit (`smtp` → lokální catcher)
- LIVE: override vypnutý
- smoke rezervace vždy na vlastní adresu

(Implementaci override doplnit v backendu, pokud ještě není — do té doby na stagingu vypnout worker / použít fake SMTP.)

---

## 6. Denní provoz (stručně)

| Čas | Akce |
|-----|------|
| Noční cron | `backup.sh` → DB + config + www |
| Před změnou | Tag `live-known-good` pokud ještě není |
| Vývoj | Branch → GitHub |
| Test | Deploy na staging → checklist |
| Promote | Merge → tag `live-…` → `deploy-live.sh` |
| Havárie | `rollback-live.sh <tag-nebo-stamp>` |

Detail checklistu syncu: `DEPLOY_SAFETY.md`.

---

## 7. Co postavit jako další kroky (pořadí)

1. ~~Záloha `www/` + safety docs~~ (hotovo)  
2. **Používat jen** `deploy-live.sh` / `rollback-live.sh` na produkci  
3. Založit `/opt/ulov-staging` + DNS `staging.` / `api-staging.`  
4. Staging SMTP override / Mailpit  
5. Volitelně: GitHub Action „deploy staging on push to branch“  
6. Hetzner snapshot disku 1× denně (mimoaplikáční pojistka)

Dokud není staging, **minimální jistota** = GitHub + pre-deploy check + záloha + rollback bod (verze 2). Staging (verze 1) přidá jistotu „100 % včetně mailů“ před veřejností.

---

## FAQ — A / B / C

### A) Jak zajistíš, že se agent (Cursor) toho vždy drží?

Technicky **nejde dát 100% železný zámek jen dokumentací** — agent může dostat výjimku, když ji schválíš. Drží se to vrstvami:

| Vrstva | Co dělá |
|--------|---------|
| **Cursor rule** `.cursor/rules/deploy-safety.mdc` (`alwaysApply: true`) | Agent vidí zákaz přímého LIVE uploadu v každé session |
| **Ty jako schvalovatel** | Smart-mode / approval u SSH na LIVE — **odmítni** příkazy typu `rsync … www/` mimo `deploy-live.sh` |
| **Jeden povolený skript** | Na serveru zvyk: LIVE jen `bash deploy/deploy-live.sh <tag>` |
| **GitHub** | Na LIVE nic, co není v `origin` (tag / main) |
| **Později CI** | Deploy jen z GitHub Actions s ručním „Approve production“ |

**Tvoje role:** když agent navrhne „rychle nahrajeme na LIVE“, napiš ne / odkaž na staging. Bez tvého YES na nebezpečný příkaz by to nemělo projít.

---

### B) Kde a jak online vyzkoušíš staging?

**Teď ještě ne** — staging stack na serveru zatím není postavený (je jen ve strategii).

Až poběží (cílový návrh):

| URL | Účel |
|-----|------|
| `https://www.staging.ulovklienty.cz/` (alias `staging.…`) | hub / presentace |
| `https://www.staging.ulovklienty.cz/beauty/` atd. | vertikály |
| `https://www.staging.ulovklienty.cz/salon1/` … | dema |
| `https://api-staging.ulovklienty.cz/` | API |

Postup: otevřeš ty URL v prohlížeči stejně jako LIVE → rezervace, admin, maily (půjdou na test schránku).  
Až řekneš „postav staging“, založíme `/opt/ulov-staging`, DNS a certifikáty.

Do té doby test = **lokál** (`localhost`) + kontrola, že vše je v GitHubu, + rollback bod před LIVE.

---

### C) Sdílená DB, nebo oddělená kopie?

**Oddělená databáze. Sdílet produkční DB se stagingem nebudeme.**

| | Sdílená DB s LIVE | Oddělená kopie (doporučeno) |
|--|-------------------|------------------------------|
| Riziko | Staging smaže/změní ostrá data | LIVE netkne |
| Rezervace | Testovací booking uvidí zákazník / zmate ostrý provoz | Jen testovací svět |
| E-maily | Snadno odejdou reálným lidem | Override na test schránku |
| Realismus | 100 % stejná data | Po obnově dumpem skoro stejná |

**Prakticky:**
1. Jednou (nebo po větší změně modelu): dump z LIVE → obnovit do `ulov_staging`
2. Nebo `seed_*` + pár ručních rezervací na stagingu („základní kopie“)
3. Staging `.env`: jiné `DB_NAME`, jiné volume, `EMAIL_OVERRIDE` / Mailpit

Sdílení Redis/DB volume mezi LIVE a staging = **zakázáno**.
