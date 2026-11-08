# Technický audit DPA MODERNÍK

| Položka | Hodnota |
|--------|---------|
| Dokument | Podmínky zpracování osobních údajů (DPA), Příloha č. 2 |
| Zdroj textu | `modernik/dpa.html` · staging https://staging.modernik.cz/dpa.html |
| Datum DPA | září 2026 |
| Datum auditu | 25. 10. 2026 |
| Rozsah | STAGING + kódová kontrola chování shodného s LIVE pipeline |
| Změny kódu / LIVE | **Žádné** (pouze analýza) |
| Související | `modernik/subzpracovatele.html`, `backend/rezervace/`, `backend/flow/`, `backend/archivnik/`, `materialnik/`, `deploy/backup.sh` |

### Metodika

- Porovnání jednotlivých tvrzení DPA s implementací v gitu (modely, API, cron, deploy).
- Žádné čtení ostrých osobních údajů zákazníků; žádné zásahy do produkčních dat.
- Výsledky: **SOULAD** / **ROZPOR** / **NELZE OVĚŘIT** / **NETÝKÁ SE**.
- Závažnost rozporů: **P0** (před LIVE kritické) … **P3** (nízká / kosmetická).

---

## Shrnutí pro rozhodnutí

Nejzávažnější rozpory, které je vhodné vyřešit **před schválením právní dokumentace / LIVE** této DPA:

1. **P0** — DPA tvrdí, že Partner **nikdy** nevidí e-mail z rezervace; systém e-mail **zpřístupňuje** v FLOW/admin API do anonymizace.
2. **P0** — DPA vyžaduje **e-mailové potvrzení** pro založení klientské karty; systém kartu zakládá **okamžitě** bez confirm linku (legacy confirm byl odstraněn).
3. **P1** — Anonymizace „do 24 h“ může být **odložena** čekáním na děkovný e-mail; po anonymizaci může zůstat **jméno/nick**.
4. **P1** — **Archivník** (telefon, adresa, objekty, fotky, alergie v presetu) není v DPA dostatečně popsán; seznam kategorií je užší než realita.
5. **P1** — Ukončení spolupráce: DPA slibuje předání/výmaz; **kompletní offboarding** partnera není automatizovaný.
6. **P2** — Incidenty a součinnost při žádostech subjektů: smluvně ano, **provozní runbook** chybí.

---

## 1. Rezervační systém a e-mail (Čl. II, III, VI)

### F1 — Čl. VI odst. 5 + Čl. VII odst. 2

| Pole | Obsah |
|------|--------|
| **DPA tvrdí** | Partner ani pracovníci **nemají po žádnou dobu** přístup k e-mailu zákazníka z rezervačního systému; e-mail není Partnerovi zpřístupněn. |
| **Systém** | Do anonymizace je e-mail dostupný jako `kontaktni_email` / `email_host` přes `AdminRezervaceSerializer` ve web adminu i FLOW kalendáři. Po `anonymized_at` API vrací prázdný řetězec. Owner NO-show archiv může e-mail zobrazit, dokud plaintext existuje. |
| **Důkaz** | `backend/rezervace/serializers.py` (`get_kontaktni_email`, `get_email_host`); `backend/flow/provoz_views.py`; `backend/rezervace/services/email_reputace.py` (`hledat_hrisniky`); model `Zakaznik.email` plaintext (`models.py`). |
| **Výsledek** | **ROZPOR** |
| **Závažnost** | **P0** |
| **Doporučení** | **Obojí možné:** (A) upravit DPA tak, aby popisovala dočasný přístup Partnera k e-mailu pro provoz rezervace do anonymizace; **nebo** (B) technicky e-mail z admin/FLOW API odstranit / maskovat (větší zásah do UX). |
| **Velikost** | Text DPA: **S** · Implementace maskování: **M–L** |

### F2 — Čl. VI odst. 4

| Pole | Obsah |
|------|--------|
| **DPA tvrdí** | E-mail je uchováván výhradně Zpracovatelem. |
| **Systém** | Uloženo v DB Zpracovatele (`Zakaznik.email` / `Rezervace.email_host`). Zároveň je ale **viditelné Partnerovi** (viz F1) — „uchováváno výhradně“ vs. „zpřístupněno“ je sporné. |
| **Důkaz** | `backend/rezervace/models.py` (`Zakaznik`, `Rezervace`); F1. |
| **Výsledek** | **ROZPOR** (ve spojení s F1 — Partner má přístup k údaji, který DPA popisuje jako výhradní u Zpracovatele) |
| **Závažnost** | **P0** |
| **Doporučení** | Sladit formulaci DPA s modelem „Zpracovatel ukládá; Partner vidí do anonymizace“. |
| **Velikost** | **S** |

### F3 — Čl. II A / Čl. VI odst. 2–3 — vznik rezervace po e-mailovém potvrzení

| Pole | Obsah |
|------|--------|
| **DPA tvrdí** | Rezervace vzniká až potvrzením přes ověřovací odkaz; nepotvrzená není dokončená. |
| **Systém** | Online booking: `stav='ceka'` + `email_vyzva_k_potvrzeni` + `potvrzeni_token`; po kliknutí `stav='potvrzeno'`. Záznam v DB ale **existuje už ve stavu `ceka`**. Staff/FLOW create typicky rovnou `potvrzeno` **bez** e-mailového odkazu (`typ_vytvoreni` telefon/zaměstnanec, e-mail volitelný). |
| **Důkaz** | `backend/rezervace/views.py` (`vytvor_rezervaci`, `RezervacePotvrditView`); `backend/flow/provoz_views.py` (`FlowRezervaceCreateView`); `backend/rezervace/services/emails.py`. |
| **Výsledek** | **ROZPOR** (částečný: online tok přibližně odpovídá „dokončení až po potvrzení“, ale (1) záznam vzniká dříve, (2) alternativní cesty bez potvrzení) |
| **Závažnost** | **P1** |
| **Doporučení** | Upravit DPA: rozlišit online rezervaci vs. rezervaci založenou personálem; upřesnit, že nepotvrzená online rezervace je dočasný záznam ve stavu čekání. |
| **Velikost** | **S** |

### F4 — Čl. II A / Čl. VI odst. 6 — účely e-mailu a automatické zprávy

| Pole | Obsah |
|------|--------|
| **DPA tvrdí** | E-mail slouží k ověření, potvrzení, změně/zrušení, systémovým oznámením, QR, poděkování, recenzi, NO-show. |
| **Systém** | Odpovídá: výzva, potvrzení, storno, připomínka (+24 h), děkovný/review (feature flag), QR/záloha (manuál), NO-show (manuál), změna obsluhy, nové heslo. Orchestruje `proved_zivotni_cyklus` / Celery tasky. |
| **Důkaz** | `backend/rezervace/services/emails.py`, `notifikace_email.py`, `tasks.py`, `zivotni_cyklus.py`. |
| **Výsledek** | **SOULAD** |
| **Závažnost** | — |
| **Doporučení** | Žádné. |
| **Velikost** | — |

### F5 — Čl. III — kategorie údajů rezervace (e-mail, nick, termín, služba, IP, audit)

| Pole | Obsah |
|------|--------|
| **DPA tvrdí** | Mimo jiné e-mail, přezdívka, datum/čas, služba, pracovník, IP, systémové ID, audit. |
| **Systém** | Pole existují: `Zakaznik.email/nick`, `Rezervace` termín/služby/zaměstnanec, `ip_adresa`, `SalonAuditLog` / `RezervaceHistorie`. |
| **Důkaz** | `backend/rezervace/models.py` (`ip_adresa` aj.); `audit.py`. |
| **Výsledek** | **SOULAD** |
| **Závažnost** | — |
| **Doporučení** | — |
| **Velikost** | — |

### F6 — Přenos e-mailu do FLOW / dalších systémů

| Pole | Obsah |
|------|--------|
| **DPA tvrdí** | (Nepřímo) rezervace automaticky nevytváří kartu; e-mail jen pro rezervaci. |
| **Systém** | FLOW **neukládá** druhou kopii rezervace — čte stejný model. Kartotéka: runtime match e-mailu; při „Založit zákazníka“ se e-mail **zkopíruje** do `archivnik.Customer.email`. Materiálník outbox bere `reservation_ref` **bez** e-mailu. |
| **Důkaz** | `backend/flow/kartoteka_services.py` (`create_customer_from_flow`, `attach_archivnik_customer_links`); materiálník enqueue v `dokonceni.py`. |
| **Výsledek** | **SOULAD** s poznámkou (kopie e-mailu nastává až při vědomém založení karty — viz F8) |
| **Závažnost** | — / souvisí s F8 |
| **Doporučení** | V DPA výslovně uvést, že při založení karty z rezervace se kontaktní údaje přenesou do Evidence (Archivník). |
| **Velikost** | **XS** |

### F7 — Čl. VI odst. 7 — zákaz marketingu z rezervačních údajů

| Pole | Obsah |
|------|--------|
| **DPA tvrdí** | Partner nesmí používat údaje z rezervací k marketingu. |
| **Systém** | Softwarově **nevynuceno** (Partner vidí e-mail — F1). Jde o smluvní povinnost Správce. |
| **Důkaz** | Absence technického blokování marketingu; F1. |
| **Výsledek** | **NELZE OVĚŘIT** technicky (smluvní závazek); riziko vyšší kvůli F1 |
| **Závažnost** | **P2** (ve spojení s F1) |
| **Doporučení** | Primárně řešit F1; případně UI upozornění. |
| **Velikost** | **S** |

---

## 2. FLOW – Evidence klientů (Čl. II B, III, VI odst. 8–15)

### F8 — Čl. VI odst. 9–11 — potvrzení karty e-mailovým odkazem

| Pole | Obsah |
|------|--------|
| **DPA tvrdí** | Karta vzniká jen na žádost Partnera **a po potvrzení zákazníkem e-mailovým odkazem**; bez potvrzení nevzniká. |
| **Systém** | `create_customer_from_flow` ukládá `Customer` **ihned**; e-mail povinný ve FLOW, ale **žádný confirm token / e-mail**. Legacy `CustomerCard` + confirm odstraněn (`flow/migrations/0005_…`). Endpoint potvrzení karty → 404 (testy P56b). Vznik: z rezervace nebo ručně (FLOW/Archivník UI). Import CSV nenalezen. |
| **Důkaz** | `backend/flow/kartoteka_services.py`; `backend/flow/migrations/0005_delete_customercard_customervisit.py`; `backend/flow/tests_p56b_legacy_cleanup.py`; `flow/customer-card.js`. |
| **Výsledek** | **ROZPOR** |
| **Závažnost** | **P0** |
| **Doporučení** | **DPA:** odstranit požadavek e-mailového potvrzení a popsat aktuální model (založení personálem + odpovědnost Správce za právní základ). **Nebo implementace:** obnovit double opt-in (**L–XL**). |
| **Velikost** | Text: **S** · Opt-in znovu: **L–XL** |

### F9 — Čl. II B / VI odst. 10 — rezervace automaticky nevytváří kartu

| Pole | Obsah |
|------|--------|
| **DPA tvrdí** | Samotná rezervace automaticky nevytváří dlouhodobou kartu. |
| **Systém** | Ano — karta jen po akci „Založit zákazníka“ / ruční create. |
| **Důkaz** | `kartoteka_services.py`; UI `customer-card.js`. |
| **Výsledek** | **SOULAD** |
| **Závažnost** | — |
| **Doporučení** | — |
| **Velikost** | — |

### F10 — Čl. III / VI odst. 12 — údaje na kartě

| Pole | Obsah |
|------|--------|
| **DPA tvrdí** | Identifikace, historie návštěv/služeb, poznámky, materiály, servisní historie, další údaje. |
| **Systém** | `archivnik.Customer`: jméno, příjmení, telefon, e-mail, adresa, poznámka, tagy; + `Object`/`Entry`/`Asset`/`Reminder`/`CustomFieldValue`. „Historie návštěv“ není samostatný legacy `CustomerVisit` — spíš zápisy + vazba na rezervace přes e-mail. Materiály na kartě přímo ne; Materiálník je oddělený. |
| **Důkaz** | `backend/archivnik/models.py`; presets `beauty.py` / `vet.py` / `pneu.py`. |
| **Výsledek** | **ROZPOR** (částečný — DPA nepojmenovává telefon/adresu/fotky/objekty; „materiály na kartě“ spíš neodpovídá) |
| **Závažnost** | **P1** |
| **Doporučení** | Rozšířit DPA o Archivník / kartotéku (kategorie polí, přílohy, objekty). U materiálů odkázat na Materiálník, ne na kartu. |
| **Velikost** | **M** |

### F11 — Čl. III — zákaz zápisu zvláštních kategorií (čl. 9 GDPR) do poznámek

| Pole | Obsah |
|------|--------|
| **DPA tvrdí** | Partner nesmí do poznámek zapisovat zvláštní kategorie bez právního základu. |
| **Systém** | Softwarově **neblokováno**. Beauty/vet preset obsahuje pole typu „Alergie“, „Citlivost / alergie“. Volný text v `Entry`/`poznamka`. |
| **Důkaz** | `backend/archivnik/presets/beauty.py`; `models.py` (`Entry`, `Customer.poznamka`). |
| **Výsledek** | **SOULAD** jako smluvní zákaz Správce; **riziko** že UI **nabádá** k zápisu zdravotních údajů |
| **Závažnost** | **P1** (produkt vs. DPA) |
| **Doporučení** | Právní: buď upravit DPA (podmíněné zpracování čl. 9), nebo upravit preset (odstranit/přejmenovat zdravotní pole) + UX varování. |
| **Velikost** | Text: **S** · Produkt: **M** |

### F12 — Čl. VI odst. 13 — oprávnění pracovníků

| Pole | Obsah |
|------|--------|
| **DPA tvrdí** | Karta jen pro oprávněné pracovníky dle oprávnění. |
| **Systém** | FLOW: platný `X-Flow-Token` + entitlement kartotéky; **bez** jemného RBAC majitel vs zaměstnanec u čtení/zápisu karty. Archivník: smazání zákazníka jen majitel. |
| **Důkaz** | `backend/flow/auth.py`, `kartoteka_views.py`; `archivnik/views.py` (delete 403 non-owner); `partner_admin/entitlements.py`. |
| **Výsledek** | **SOULAD** na úrovni „jen přihlášený staff tenanta“; **slabší** než „granulární oprávnění“ |
| **Závažnost** | **P2** |
| **Doporučení** | Upravit DPA na „oprávnění pracovníci s přístupem do FLOW/Archivníku“, nebo doplnit RBAC (**L**). |
| **Velikost** | Text: **XS** · RBAC: **L** |

### F13 — Izolace Partnerů (tenant)

| Pole | Obsah |
|------|--------|
| **DPA tvrdí** | (Čl. IV/IX) ochrana; audit bez přístupu k údajům jiných Partnerů. |
| **Systém** | Aplikační filtr `salon_id`; testy cross-tenant. Shared PostgreSQL (ne DB-per-tenant). |
| **Důkaz** | `backend/flow/tests_kartoteka.py`; Archivník testy tenant izolace. |
| **Výsledek** | **SOULAD** (aplikační izolace doložená) |
| **Závažnost** | — |
| **Doporučení** | — |
| **Velikost** | — |

---

## 3. Uchovávání, anonymizace, NO-show (Čl. VII)

### F14 — Čl. VII odst. 3 — anonymizace do 24 h

| Pole | Obsah |
|------|--------|
| **DPA tvrdí** | Nejpozději do 24 h od skončení služby je e-mail v rezervaci anonymizován tak, že osobu nelze identifikovat. |
| **Systém** | Cron `rezervace_zivotni_cyklus` (Docker `cron` ~1×/h). `ANONYMIZACE_PO_HODINACH = 24`. Podmínka: stav po službě + `now >= konec + 24h`. U `dokonceno` s aktivním děkovným mailem **čeká na `thank_you_sent_at`** → může být **déle než 24 h**. Anonymizace maže e-mail/poznámku; **ne** `jmeno_host` / `Zakaznik.nick`. Stavy `ceka`/`potvrzeno` se **neanonymizují**, dokud nejsou dokončeny/stornovány. |
| **Důkaz** | `backend/rezervace/services/gdpr.py`; `zivotni_cyklus.py` (`muze_anonymizovat`, `_anonymizovat_vhodne`); `docker-compose.yml` služba `cron`; `ZIVOTNI_CYKLUS_REZERVACE.md`. |
| **Výsledek** | **ROZPOR** (lhůta i „nelze identifikovat“) |
| **Závažnost** | **P1** |
| **Doporučení** | DPA: „zpravidla do 24 h po splnění podmínek dokončení/storno; u děkovného mailu po jeho odeslání“ + uvést, že provozní identifikátory (nick/jméno) mohou zůstat / nebo doplnit mazání jména v kódu. |
| **Velikost** | Text: **S** · Doplnit mazání jména: **S** |

### F15 — Čl. VII odst. 4 — NO-show hash + 12 měsíců

| Pole | Obsah |
|------|--------|
| **DPA tvrdí** | E-mail anonymizován do 24 h; hash + provozní údaje max 12 měsíců; pak výmaz; jen ochrana systému. |
| **Systém** | `NoShowZaznam` s plaintext e-mailem do anonymizace rezervace, pak `email=''`, `email_hash` = SHA-256 (jednosměrný). Úklid: `NoShowZaznam.objects.filter(vytvoreno__lt=hranice).delete()` kde hranice = ~12×30 dní. Reputace/blokace v salonu. |
| **Důkaz** | `gdpr.py` (`email_hash`); `zivotni_cyklus.py` (`_vycistit_stare_zaznamy`); `email_reputace.py`. |
| **Výsledek** | **SOULAD** (s poznámkou: 12 měsíců = 360 dní, ne kalendářní měsíce) |
| **Závažnost** | **P3** (drobná nepřesnost lhůty) |
| **Doporučení** | Volitelně sjednotit „12 měsíců“ vs. `30*12` dní. |
| **Velikost** | **XS** |

### F16 — Hash reverzibilita

| Pole | Obsah |
|------|--------|
| **DPA tvrdí** | Hash e-mailu (ochrana systému). |
| **Systém** | `hashlib.sha256(normalized.lower())` — **ne** kryptograficky reverzibilní; při známém e-mailu lze ověřit shodu (záměr pro blokaci). |
| **Důkaz** | `backend/rezervace/services/gdpr.py` → `email_hash`. |
| **Výsledek** | **SOULAD** |
| **Závažnost** | — |
| **Doporučení** | — |
| **Velikost** | — |

### F17 — Zálohy a logy po anonymizaci

| Pole | Obsah |
|------|--------|
| **DPA tvrdí** | (Obecně výmaz; Čl. XII kopie) |
| **Systém** | `deploy/backup.sh`: `BACKUP_KEEP_DAYS` default **14** — anonymizovaný plaintext může zůstat v `pg_dump` až ~14 dní. Aplikační logy nemají v repo dedikovanou retenci. Audit scrub maže klíče s `email` v historii rezervace při anonymizaci. |
| **Důkaz** | `deploy/backup.sh`; `gdpr.py` (`_scrub_historie`). |
| **Výsledek** | **NELZE OVĚŘIT** plný soulad s „výmazem“ bez zmínky záloh; **riziko** |
| **Závažnost** | **P2** |
| **Doporučení** | Doplnit do DPA větu o přetrvání v zálohách po dobu retenční politiky záloh (např. 14 dní). |
| **Velikost** | **XS** |

### F18 — Čl. VII odst. 7 — anonymizované statistiky 12 měsíců

| Pole | Obsah |
|------|--------|
| **DPA tvrdí** | Anonymizované statistiky až 12 měsíců. |
| **Systém** | Soft-delete rezervací po ~12 měsících; dedikovaný „statistický“ store mimo rezervace **není** v kódu zřetelně oddělen. |
| **Důkaz** | `zivotni_cyklus.py` (`muze_smazat`, `_smazat_vyprsale`). |
| **Výsledek** | **NELZE OVĚŘIT** (obecná formulace; chybí samostatný statistický dataset) |
| **Závažnost** | **P3** |
| **Doporučení** | Upřesnit, co se považuje za anonymizovanou statistiku, nebo formulaci zúžit. |
| **Velikost** | **XS** |

---

## 4. Materiálník a Archivník

### F19 — Čl. II D / VI odst. 16 — Materiálník

| Pole | Obsah |
|------|--------|
| **DPA tvrdí** | Evidence materiálu/spotřeby + údaje o pracovnících Partnera. |
| **Systém** | Modely skladu, `StaffSession`, dodavatelé; **ne** PII koncových zákazníků; `reservation_ref` jako ID. Tenant middleware. |
| **Důkaz** | `materialnik/sklad/models.py`, `middleware.py`. |
| **Výsledek** | **SOULAD** |
| **Závažnost** | — |
| **Doporučení** | — |
| **Velikost** | — |

### F20 — Archivník — pokrytí DPA

| Pole | Obsah |
|------|--------|
| **DPA tvrdí** | Evidence klientů pod FLOW; Archivník **nejmenuje**. |
| **Systém** | Archivník = produkční modul + úložiště Bunny; FLOW kartotéka je proxy na `archivnik.models.*`. Zvířata/vozidla/profily, zápisy, fotky, custom fields. |
| **Důkaz** | `backend/archivnik/`; `backend/flow/kartoteka_views.py`; `archivnik/storage.py`. |
| **Výsledek** | **ROZPOR** (opomenutí existujícího zpracování / neúplný popis) |
| **Závažnost** | **P1** |
| **Doporučení** | **Rozšířit DPA** (a případně Přílohu kategorií): Archivník jako součást Evidence / samostatný režim; kategorie údajů; Bunny už je v subzpracovatelích. |
| **Velikost** | **M** |

### F21 — Čl. I odst. 6 — předmět zahrnuje FLOW a Materiálník

| Pole | Obsah |
|------|--------|
| **DPA tvrdí** | Předmět zahrnuje rezervace, FLOW, Materiálník a další sjednané funkce. |
| **Systém** | Odpovídá architektuře; „další funkce“ pokrývá Archivník jen nepřímo. |
| **Důkaz** | Specifikace produktů; entitlements. |
| **Výsledek** | **SOULAD** s mezerou F20 |
| **Závažnost** | — |
| **Doporučení** | Explicitně zmínit Archivník / kartotéku. |
| **Velikost** | **XS** |

---

## 5. Subzpracovatelé (Čl. VIII + Příloha č. 3)

### F22 — Seznam vs. realita

| Subzpracovatel / služba | V seznamu | Skutečnost | PII | Mimo EHP | Verdikt |
|-------------------------|-----------|------------|-----|----------|---------|
| Hetzner (hosting, DB, Redis, zálohy na VPS) | Ano | Ano | Celá DB | Ne (DE) | **SOULAD** |
| Bunny.net (CDN/storage) | Ano | Ano (web média + Archivník assety) | Fotky/dokumenty | CDN edge možné | **SOULAD** |
| SMTP Partnera | Poznámka „není subzpracovatel Hakla“ | Ano | Transakční mail | Dle Partnera | **SOULAD** (model správný) |
| Sentry | „Nepoužíváme“ | Kód připraven (`SENTRY_DSN`); `send_default_pii=False` | Při zapnutí rizika | Typ. USA | **NELZE OVĚŘIT** LIVE DSN bez přístupu k tajemství; pokud DSN prázdný → soulad |
| GA4 | „Nepoužíváme pro data Partnera“ | `gaMeasurementId: ""` | — | — | **SOULAD** (neaktivní) |
| AI služby | „Nepoužíváme“ | V provozu nenalezeno; VOP/DPA zakazují libovolné předání | — | — | **SOULAD** |
| Stripe | — | Neaktivní | — | — | **NETÝKÁ SE** |
| Forpsi DNS / platform SMTP Ulov | Není v modernik seznamu | Onboarding/docs | Okrajové | EU | **P2** — zvážit, zda patří do inventáře |

**Důkazy:** `modernik/subzpracovatele.html`; `docker-compose.yml`; `backend/salons/bunny.py`; `backend/salon_api/settings.py` (Sentry); `deploy/backup.sh`.

### F23 — Čl. VIII odst. 5 — předchozí oznámení změn subzpracovatelů

| Pole | Obsah |
|------|--------|
| **DPA tvrdí** | Předem informovat Správce; námitky; aktualizace seznamu. |
| **Systém** | Proces v kódu **není**; jde o provozní/právní postup. |
| **Důkaz** | Absence automatizace. |
| **Výsledek** | **NELZE OVĚŘIT** |
| **Závažnost** | **P2** |
| **Doporučení** | Ops checklist při změně infrastruktury. |
| **Velikost** | **S** (proces) |

### F24 — Čl. VIII odst. 6 — předání mimo EHP

| Pole | Obsah |
|------|--------|
| **DPA tvrdí** | Mechanismy GDPR (SCC / adequacy). |
| **Systém** | Bunny CDN může mít edge mimo EHP — seznam to připouští. Konkrétní SCC dokumentace v repo **není**. |
| **Důkaz** | `subzpracovatele.html`; Bunny docs mimo repo. |
| **Výsledek** | **NELZE OVĚŘIT** (smluvní mechanismus u Bunny) |
| **Závažnost** | **P2** |
| **Doporučení** | Doplnit odkaz na DPA/SCC Bunny v interní složce / poznámce Přílohy 3. |
| **Velikost** | **S** |

---

## 6. Bezpečnost a incidenty (Čl. IV, IX)

### F25 — Čl. IX — autentizace, oprávnění, přenos, zálohy, audit

| Pole | Obsah |
|------|--------|
| **DPA tvrdí** | Řízení oprávnění, autentizace, ochrana přenosu, zálohování, evidence přístupů, ochrana proti neoprávněnému přístupu. |
| **Systém** | Tokeny FLOW/Staff/Archivník; HTTPS (nginx/LE); zálohy `backup.sh`; `SalonAuditLog` + GDPR audit kategorie; tenant filtr. |
| **Důkaz** | `flow/auth.py`, `staff_auth.py`, `archivnik/auth.py`, `audit.py`, `backup.sh`. |
| **Výsledek** | **SOULAD** (na úrovni existence opatření) |
| **Závažnost** | — |
| **Doporučení** | — |
| **Velikost** | — |

### F26 — Čl. IV písm. e + odst. 2 — oznámení incidentu Partnerovi

| Pole | Obsah |
|------|--------|
| **DPA tvrdí** | Bez zbytečného odkladu oznámit porušení; obsah oznámení. |
| **Systém** | Smluvní závazek ano; **runbook / šablona / ticket flow v repo chybí**. |
| **Důkaz** | DPA text; grep runbooků — `DEPLOY_SAFETY.md` ≠ GDPR incident. |
| **Výsledek** | **NELZE OVĚŘIT** provozní schopnost |
| **Závažnost** | **P1** (před LIVE dokumentací rizika) |
| **Doporučení** | Vytvořit krátký incident runbook (kontakt Partnera, šablona, lhůty) — **bez změny DPA**. |
| **Velikost** | **S** |

### F27 — Čl. IV písm. d/f + Čl. X — součinnost / audit / práva subjektů

| Pole | Obsah |
|------|--------|
| **DPA tvrdí** | Součinnost, informace pro soulad, přiměřený audit; součinnost při žádostech subjektů. |
| **Systém** | Nástroje: GDPR export/výmaz majitele (`…/admin/gdpr/export|vymaz/`), Archivník ZIP export. Chybí interní proces/SLA (`For Compliance v1.md` §14 to přiznává). |
| **Důkaz** | `gdpr_admin.py`; `export_archivnik_customer.py` / `export_archivnik_partner`; `For Compliance v1.md`. |
| **Výsledek** | **SOULAD** částečně (nástroje); **NELZE OVĚŘIT** end-to-end proces |
| **Závažnost** | **P2** |
| **Doporučení** | Ops proces + odkaz ve vnitřní dokumentaci. |
| **Velikost** | **S–M** |

### F28 — Čl. IX odst. 5 — AI

| Pole | Obsah |
|------|--------|
| **DPA tvrdí** | AI neopravňuje k předání PII libovolným AI; subzpracovatelé v Příloze 3. |
| **Systém** | AI subprocessor v provozu nenalezen. |
| **Důkaz** | `subzpracovatele.html`; absence OpenAI/Anthropic v runtime. |
| **Výsledek** | **SOULAD** |
| **Závažnost** | — |
| **Doporučení** | — |
| **Velikost** | — |

---

## 7. Ukončení a výmaz (Čl. XII)

### F29 — Čl. XII odst. 3 — výmaz nebo předání + výmaz

| Pole | Obsah |
|------|--------|
| **DPA tvrdí** | Po ukončení služeb Zpracovatel podle volby Správce údaje vymaže, nebo předá a pak vymaže kopie (výjimky zákonné). |
| **Systém** | Částečné exporty: GDPR JSON (zákazník), Archivník ZIP (karta / partner exit — **nemáže**). Deaktivace Materiálníku **nemáže** data. **Chybí** automatický `purge_salon` / offboarding (DB + Bunny prefix + www + zálohy). Retence běžných rezervací běží jen u aktivního provozu. |
| **Důkaz** | `gdpr_admin.py`; `archivnik/kartoteka_export.py`; `partner_admin/services_moduly.py`; absence offboarding runbooku. |
| **Výsledek** | **ROZPOR** (slib vs. operationalizace) |
| **Závažnost** | **P1** |
| **Doporučení** | Buď DPA zmírnit („bez zbytečného odkladu přiměřenými prostředky / součinnost“), nebo dodat offboarding runbook + skripty (**L–XL**). |
| **Velikost** | Text: **S** · Implementace: **L–XL** |

### F30 — NO-show po ukončení služby

| Pole | Obsah |
|------|--------|
| **DPA tvrdí** | Údaje jen pro provoz/bezpečnost vč. NO-show se po ukončení služby vymažou (není-li právní důvod). |
| **Systém** | Automatický wipe NO-show při offboardingu partnera **není**; pouze retenční cron u starých záznamů. |
| **Důkaz** | F29; `zivotni_cyklus.py`. |
| **Výsledek** | **ROZPOR** / závisí na manuálním zásahu |
| **Závažnost** | **P2** |
| **Doporučení** | Součást offboardingu. |
| **Velikost** | **M** (v rámci offboardingu) |

---

## 8. Ostatní články I–XIII a návaznosti

### F31 — Čl. I — identifikace Správce/Zpracovatele, MODERNÍK ≠ zpracovatel

| Pole | Obsah |
|------|--------|
| **Výsledek** | **SOULAD** s modelem VOP/Smlouvy (Jiří Hakl = poskytovatel/zpracovatel). |
| **Důkaz** | `dpa.html` lead; `smlouva.html`; `vop.html`. |
| **Závažnost** | — |

### F32 — Čl. V — povinnosti Správce

| Pole | Obsah |
|------|--------|
| **Výsledek** | **NETÝKÁ SE** technické implementace (právní povinnosti Partnera); nástroje součinnosti viz F27. |
| **Závažnost** | — |

### F33 — Čl. XI — mlčenlivost

| Pole | Obsah |
|------|--------|
| **Výsledek** | **NELZE OVĚŘIT** (organizační; v kódu jen přístupová kontrola). |
| **Závažnost** | **P3** |

### F34 — Čl. XIII — účinnost / změny / vztah k VOP

| Pole | Obsah |
|------|--------|
| **DPA tvrdí** | Nedílná součást Smlouvy; změny dle Smlouvy/VOP. |
| **Systém / dokumenty** | VOP 2.2 účinné 24. 10. 2026; DPA stále „září 2026“ — **datová neaktuálnost**. Odkazy na smlouvu/VOP/subzpracovatele funkční. |
| **Důkaz** | `dpa.html` meta; `vop.html` 24. 10. 2026. |
| **Výsledek** | **ROZPOR** (aktuálnost data dokumentu) |
| **Závažnost** | **P3** |
| **Doporučení** | Aktualizovat datum DPA při schválení oprav. |
| **Velikost** | **XS** |

### F35 — Rozpor se Smlouvou / Specifikací / VOP v2.2

| Pole | Obsah |
|------|--------|
| **Zjištění** | Produktový model START/PRO/Materiálník/Program Růstu ve VOP/Smlouvě/Specifikaci DPA obecně nekoliduje. Kolize je spíš DPA ↔ **implementace** (F1, F8), ne DPA ↔ VOP. Archivník ve Specifikaci/VOP jako „evidence“ přes FLOW — DPA zaostává. |
| **Výsledek** | **SOULAD** s VOP/Smlouvou na úrovni smluvní hierarchie; **ROZPOR** s realitou systému viz výše |
| **Závažnost** | viz F1/F8/F20 |

### F36 — Čl. VI odst. 1 — rezervace „výhradně“ k vytvoření/správě

| Pole | Obsah |
|------|--------|
| **Výsledek** | **SOULAD** (účelové omezení); marketing zákaz viz F7. |
| **Závažnost** | — |

---

## Tabulka subzpracovatelů (provozní inventář)

| Subjekt | Účel | Data | Oblast | Subzpracovatel Hakla? | V Příloze 3? |
|---------|------|------|--------|----------------------|--------------|
| Hetzner Online GmbH | Hosting, DB, Redis, app, lokální zálohy | Veškerá provozní PII | DE | Ano | Ano |
| BunnyWay d.o.o. | CDN/storage médií + Archivník soubory | Fotky, dokumenty | EU + možné edge mimo EHP | Ano (u OÚ médií) | Ano |
| SMTP Partnera | Transakční e-maily | E-mail, jméno, termín | Dle Partnera | Ne (vztah Partner–SMTP) | Poznámka |
| Sentry | Volitelný monitoring | Stack/request (riziko) | Typ. mimo EHP | Ano **pokud zapnuto** | Ne („nepoužíváme“) |
| Google Analytics | Hub/modernik cookies | Návštěvníci webu Ulov | — | Neaktivní | Ne |

---

## Statistiky

| Metrika | Počet |
|---------|------:|
| Zkontrolovaná ustanovení / zjištění (F1–F36) | **36** |
| **SOULAD** (včetně částečných označených jako SOULAD) | **14** |
| **ROZPOR** | **12** |
| **NELZE OVĚŘIT** | **8** |
| **NETÝKÁ SE** | **2** |
| Rozpory **P0** | **3** (F1, F2, F8) |
| Rozpory / rizika **P1** | **7** (F3, F10, F11, F14, F20, F26, F29) |

*Pozn.: některá zjištění mají smíšený verdikt; do ROZPOR počítána ta s jasným nesouladem tvrzení vs. kód.*

---

## Seznam neověřených tvrzení

1. Plný provozní postup oznámení bezpečnostního incidentu Partnerovi (F26).  
2. End-to-end proces vyřízení žádosti subjektu údajů včetně lhůt (F27).  
3. Zda je na LIVE nastaven `SENTRY_DSN` (F22).  
4. Konkrétní SCC / mechanismus Bunny pro edge mimo EHP (F24).  
5. Organizační mlčenlivost osob Zpracovatele (F33).  
6. Proces předchozího oznamování změn subzpracovatelů (F23).  
7. Obsah a existence samostatných „anonymizovaných statistik“ (F18).  
8. Skutečná retence aplikačních logů na serveru mimo `backup.sh` (F17).

---

## Rizika nutná k řešení před LIVE (schválení této DPA)

| Priorita | ID | Riziko |
|----------|-----|--------|
| P0 | F1/F2 | DPA slibuje neviditelnost e-mailu Partnerovi — systém e-mail ukazuje. Právní i důvěryhodnostní riziko. |
| P0 | F8 | DPA slibuje double opt-in karty — systém kartu zakládá bez potvrzení. |
| P1 | F14 | Anonymizace „do 24 h / nelze identifikovat“ neodpovídá přesně kódu. |
| P1 | F20/F10/F11 | Archivník + možné zdravotní údaje mimo popis DPA. |
| P1 | F29 | Offboarding / výmaz po ukončení není plně připraven. |
| P1 | F26 | Chybí incident runbook. |

---

## Doporučené pořadí dalších kroků

1. **Právní rozhodnutí k F1:** upravit text DPA (dočasný přístup Partnera), **nebo** zadat vývoj maskování e-mailu.  
2. **Právní rozhodnutí k F8:** upravit DPA (bez e-mail confirm), **nebo** zadat obnovení opt-in.  
3. **Textové opravy DPA (S–M):** F3, F6, F10, F14, F17, F20, F34 + datum dokumentu.  
4. **Archivník / čl. 9 (F11, F20):** rozšířit DPA a/nebo upravit beauty preset.  
5. **Ops (bez změny produktu):** incident runbook (F26), DSR checklist (F27), ověření LIVE `SENTRY_DSN`.  
6. **Offboarding (F29/F30):** runbook + později skripty; mezitím upravit Čl. XII na reálnou součinnost.  
7. Až po schválení textu DPA → staging nasazení HTML; **LIVE až po výslovném schválení**.

---

## Klíčové technické reference (rychlý index)

| Oblast | Cesta |
|--------|--------|
| DPA | `modernik/dpa.html` |
| Subzpracovatelé | `modernik/subzpracovatele.html` |
| Modely rezervace / NO-show | `backend/rezervace/models.py` |
| Hash + anonymizace | `backend/rezervace/services/gdpr.py` |
| Cron životní cyklus | `backend/rezervace/services/zivotni_cyklus.py` |
| Admin e-mail ve serializeru | `backend/rezervace/serializers.py` |
| Kartotéka FLOW | `backend/flow/kartoteka_services.py` |
| Archivník | `backend/archivnik/models.py` |
| Materiálník | `materialnik/sklad/models.py` |
| Zálohy | `deploy/backup.sh` |
| Dokumentace cyklu | `ZIVOTNI_CYKLUS_REZERVACE.md` |
| Compliance notes | `For Compliance v1.md` |

---

*Konec auditu. Žádné změny DPA, kódu ani LIVE nebyly provedeny.*
