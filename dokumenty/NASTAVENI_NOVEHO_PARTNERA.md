# Nastavení nového partnera (od nuly po vlastní doménu)

Interní návod pro člověka. Platí pro **jakýkoli typ provozovny** — postup je stejný.  
Technické detaily a příkazy: [`deploy/PARTNER_ONBOARDING_RUNBOOK.md`](../deploy/PARTNER_ONBOARDING_RUNBOOK.md).

Pipeline vždy:

**lokál → GitHub DEV → staging → (schválení) → MAIN → LIVE → vlastní doména**

LIVE jen po výslovném souhlasu. Žádný přímý upload mimo git.

---

## Co si připrav předem

| Položka | Poznámka |
|---------|----------|
| Název provozovny | Oficiální jméno partnera |
| Kontakt | adresa, telefon, e-mail na webu |
| Login majitele | **unikátní e-mail** (nesmí už existovat u jiného partnera) |
| Doména webu | např. `partner.cz` / `partner.cloud` (u registrátora) |
| Schránka | ideálně `info@…` u poskytovatele (SMTP + IMAP) |
| Heslo schránky | pro odchozí maily a FLOW Mail |

---

## Fáze 1 — Partner v administraci (staging)

1. Otevři **partner-admin** na stagingu.
2. **Nový partner** — vyplň základní údaje + e-mail a heslo majitele + zapni FLOW.
3. Poznamenej si **ID partnera** (číslo salonu v systému) — musí sedět s webem.
4. V detailu partnera doplň později fakturaci / doménu podle potřeby.

---

## Fáze 2 — Web partnera v gitu

1. Nová **izolovaná složka** webu (jeden partner = jedna složka).
2. Ve webu nastav stejné **ID** jako v administraci.
3. Napoj **rezervace** a vstup majitele do **FLOW** (společný modul — nekopíruj ručně z jiného webu).
4. Web musí být kompletní: minimálně `index.html` (+ obvykle styly a skripty). Neúplnou složku **nikdy** nenasazuj.

Neměň weby jiných partnerů „jen tak“.

---

## Fáze 3 — Staging

1. Commit + push na větev **DEV**.
2. Deploy na staging.
3. Ověř:
   - veřejný web
   - rezervace (vytvoření → e-mail → potvrzení)
   - přihlášení majitele (⚙) → **Přejít do FLOW**
   - kalendář / zákazníci ve FLOW
4. V záložce **E-mail** nastav SMTP (a volitelně IMAP pro schránku ve FLOW).  
   Po uložení musí status ukazovat **Od:** jméno partnera + jeho schránku — ne globální Ulov.
5. Vyplň **URL stránky rezervací** (odkazy v e-mailech) na stagingovou adresu webu.

Stagingové maily jdou na interní override — ne ostrým zákazníkům.

---

## Fáze 4 — LIVE

1. Až staging schválíš: merge **DEV → MAIN**.
2. Deploy **LIVE** (záloha + checklist; bez mazání souborů cizích webů).
3. Partner musí existovat i v **ostré DB** se **stejným ID** jako na webu.
4. Login majitele na LIVE: e-mail musí být unikátní napříč celou LIVE DB.
5. Znovu nastav / zkontroluj:
   - SMTP + heslo schránky (+ IMAP, pokud má mít FLOW Mail)
   - URL rezervací → už LIVE adresa (Ulov cesta nebo vlastní doména)
6. Smoke: web, rezervace, FLOW, e-mailový test.

Dočasné heslo majiteli hned změň.

---

## Fáze 5 — Vlastní doména + SSL

### Ty u registrátora (DNS)

1. Najdi záznam **A** apex domény.
2. Přepiš IP na server Ulovu (aktuálně Hetzner LIVE).
3. **Neměň** MX, SPF, DKIM, DMARC, autoconfig — ať mail dál funguje.
4. `www` často řeší wildcard CNAME na apex — pak nepřidávej druhý A zbytečně.
5. Počkej na propagaci; ověř, že apex ukazuje na správnou IP.

### My na serveru

1. Nginx vhost pro doménu → složka webu partnera + `/shared/`.
2. Let's Encrypt certifikát (HTTPS).
3. Do API povolit CORS (a CSRF) pro `https://domena` a `https://www.domena`.
4. URL rezervací v nastavení partnera přepnout na `https://www.…/rezervace.html` (nebo apex).
5. Kontrola: HTTPS 200 na `/`, rezervace, sdílené styly; stará Ulov cesta může zůstat jako záloha.

---

## Rychlý checklist „jsme live“

- [ ] Web na Ulov cestě i/nebo vlastní doméně
- [ ] Rezervace + potvrzovací e-mail s funkčním tlačítkem
- [ ] Majitel: web-admin + FLOW stejným e-mailem
- [ ] Maily odcházejí ze schránky partnera
- [ ] HTTPS na vlastní doméně (zámek v prohlížeči)
- [ ] Heslo majitele předáno / změněno

---

## Časté pasti (bez zbytečné historie)

| Symptom | Typická příčina |
|---------|-----------------|
| E-mail bez tlačítka potvrzení | Chybí / je `localhost` v URL rezervací |
| „Od:“ je Ulov, ne partner | Není uložené heslo SMTP schránky partnera |
| Login „e-mail už existuje“ | Stejný e-mail má jiný partner / účet |
| SSL nejde vystavit | DNS A ještě neukazuje na Hetzner |
| Po DNS nefunguje mail | Omylem smazané MX / TXT |

---

*Související: [`deploy/DEPLOY_PIPELINE.md`](../deploy/DEPLOY_PIPELINE.md), [`deploy/DEPLOY_SAFETY.md`](../deploy/DEPLOY_SAFETY.md), [`shared/OWNER_FLOW_WIRING.md`](../shared/OWNER_FLOW_WIRING.md).*
