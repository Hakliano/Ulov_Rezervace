# Strategie bezpečného deploye (statika + LIVE)

Cíl: **nikdy znovu nepřepsat produkční weby neúplným zdrojem** a vždy mít z čeho obnovit.

---

## 1. Principy

| Princip | Pravidlo |
|---------|----------|
| Jedna pravda | Kompletní frontend žije v **gitu**. LIVE `www/` je jen nasazená kopie. |
| Kompletnost | Složka salonu/dema se nenasazuje, pokud chybí veřejný web (`index.html`, typicky i `style.css`, `app.js`). |
| Záloha před zápisem | Před každým syncem do `www/` existuje čerstvá záloha (script + snapshot). |
| Žádné tiché mazání | `rsync --delete` jen po `--dry-run` a vědomém souhlasu. |
| Ověření po | HTTP 200 + smoke (obsah se načte, ne 403/prázdný index). |

---

## 2. Co se stalo (incident 2026-07-20) — postmortem

### Shrnutí

Demo weby **Silver (demo7)** a **RELAX (demo8)** běžely kompletně na LIVE v `/opt/ulov/www/salon7|8/`, ale **nebyly v gitu** (ani kompletně lokálně).

Do gitu se commitly **neúplné** složky `salon7`/`salon8` (jen admin/rezervace JS, **bez** `index.html` / `style.css`).

Deploy na Hetzner udělal:

```bash
git reset --hard origin/main
rsync -a --delete /opt/ulov/salon7/ /opt/ulov/www/salon7/
rsync -a --delete /opt/ulov/salon8/ /opt/ulov/www/salon8/
```

`--delete` smazal na LIVE soubory, které v novém zdroji chyběly → **403 Forbidden**.  
Záloha `www/` neexistovala → HTML/CSS **neobnovitelné**.

### Kořenové příčiny

1. Dva zdroje pravdy (LIVE `www/` ≠ git).
2. Neúplný stav se commitnul a pushnul.
3. Sync s `--delete` bez dry-run / checklistu kompletnosti.
4. `deploy/backup.sh` zálohoval DB + config, **ne** `www/`.

### Náprava procesů (od teď)

- Tento dokument + Cursor rule `.cursor/rules/deploy-safety.mdc`
- `backup.sh` zálohuje i `www/`
- Checklist a preferovaný deploy postup níže

---

## 3. Checklist před LIVE deployem statiky

Označit před každým nasazením salonů / presentace / vertikálních dem:

- [ ] Všechny měněné weby jsou v gitu (commit + push), ne jen na disku PC
- [ ] Každá syncovaná složka má minimálně: `index.html` (u dema i `style.css`, `app.js`)
- [ ] Lokálně ověřeno v prohlížeči (ne jen „soubory existují“)
- [ ] Spuštěno `bash deploy/backup.sh` na serveru
- [ ] Extra: `tar` snapshot `www/` (viz níže)
- [ ] `rsync --dry-run` prohlédnut — žádné neočekávané `deleting …`
- [ ] Až pak ostrý sync; `--delete` jen pokud dry-run sedí a je to záměr
- [ ] Po: curl 200 na změněné URL; u dem s API ověřit načtení obsahu

**Stop pravidlo:** chybí `index.html` ve zdroji → **nesyncovat** tu složku (přeskočit / opravit / stáhnout z LIVE do gitu nejdřív).

---

## 4. Doporučený postup syncu `www/`

Na serveru (`/opt/ulov`):

```bash
# 1) standardní záloha (DB + config + www)
bash deploy/backup.sh

# 2) pojistný snapshot těsně před syncem
tar -czf "/root/www-predeploy-$(date +%Y%m%d_%H%M%S).tar.gz" -C /opt/ulov www

# 3) po git pull — dry-run jedné složky
rsync -a --delete --dry-run /opt/ulov/salon2/ /opt/ulov/www/salon2/ | head

# 4) ostrý sync jen když dry-run OK
# rsync -a --delete /opt/ulov/salon2/ /opt/ulov/www/salon2/

# 5) ověření
curl -sS -o /dev/null -w "%{http_code}\n" https://demo2.ulovklienty.cz/
```

Bezpečnější varianta bez mazání (pokud nepřidáváš/nečistíš soubory):

```bash
rsync -a /opt/ulov/salon2/ /opt/ulov/www/salon2/   # bez --delete
```

---

## 5. Obnova `www/` ze zálohy

Po aktualizaci `backup.sh` vznikají soubory `www_YYYYMMDD_HHMMSS.tar.gz` v `backups/`.

```bash
cd /opt/ulov
# prohlédnout
tar -tzf backups/www_NEJNOVEJSI.tar.gz | head
# obnovit (pozor — přepíše aktuální www)
tar -xzf backups/www_NEJNOVEJSI.tar.gz
# nebo z /root/www-predeploy-….tar.gz
```

---

## 6. Pravidla pro AI agenta / Cursor

Viz `.cursor/rules/deploy-safety.mdc` (always apply).

Stručně: žádný produkční `rsync --delete` / hard reset bez zálohy a checklistu; neúplný salon se nenasazuje.

---

## 7. Související soubory

| Soubor | Účel |
|--------|------|
| `deploy/backup.sh` | Denní + před-deploy záloha včetně `www/` |
| `deploy/restore.sh` | Obnova DB/config (www obnovovat z `www_*.tar.gz` dle sekce 5) |
| `NASAZENI_PRODUKCE.md` | Hlavní runbook — odkazuje sem |
| `.cursor/rules/deploy-safety.mdc` | Pravidlo pro agenta |

---

## 8. Docker DNS — kolize `api` (incident 2026-07-20)

Staging API **nesmí** na síti `ulov_default` sdílet service name `api` s LIVE.
Důsledek: nginx střídá LIVE/staging upstream → na demo* střídavě 200 a 400 (DisallowedHost) bez CORS.

Správně: služba `staging-api`, kontejner `ulov-staging-api`, nginx `proxy_pass` na `ulov-staging-api:8000`.
