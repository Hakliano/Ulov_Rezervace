# For Compliance v1

**Systém:** Ulov Rezervaci  
**Verze dokumentu:** 1.3  
**Datum:** červenec 2026  
**Rozsah:** GDPR, osobní údaje, účty, přístupová práva, audit, životní cyklus dat  
**Stav produktu:** funkční MVP s compliance hardeningem (rate limit, GDPR evidence, admin nástroje) — před produkcí doporučeno HTTPS a PostgreSQL (viz kapitola 9)

---

## 1. Účel dokumentu

Tento dokument popisuje, **jak platforma Ulov Rezervaci zpracovává osobní údaje**, jak jsou řízeny **uživatelské účty** a **přístupová práva**, a jaké **technické a organizační kontroly** jsou v systému implementovány. Slouží jako podklad pro:

- compliance / DPO review,
- smlouvu o zpracování (DPA) mezi provozovatelem platformy a salony,
- interní audit a dokumentaci pro ÚOOÚ (na žádost).

Doplňující technické detaily: `ZIVOTNI_CYKLUS_REZERVACE.md`, `TECHNICKE_NASAZENI.md`.  
Veřejný text pro zákazníky salonu: `salon*/ochrana-osobnich-udaju.html`.

---

## 2. Architektura a role v GDPR

### 2.1 Multi-tenant model

- Jeden backend obsluhuje **více salonů** (tenantů).
- Data jsou izolována přes `salon_id` (cizí klíč na model `Salon`).
- **Data mezi salony se nesdílejí** (zákazníci, NO-show archiv, blokace e-mailů).

### 2.2 Role správce vs. zpracovatele

| Role | Kdo | Odpovědnost |
|------|-----|-------------|
| **Správce** (vůči zákazníkovi salonu) | Provozovatel salonu (majitel / majitelka) | Účel rezervací, kontakt se zákazníkem, obsah webu, nastavení SMTP |
| **Zpracovatel** (technický provoz) | Provozovatel platformy Ulov Rezervaci | Hosting API, databáze, automatický životní cyklus dat, agregované statistiky |
| **Subjekt údajů** | Zákazník salonu | Osoba rezervující termín |
| **Uživatel s oprávněním** | Majitelka, zaměstnanec salonu | Přístup do administrace rezervací a webu |

> **Poznámka pro compliance:** Finální právní vymezení správce/zpracovatele musí být potvrzeno ve smlouvě mezi platformou a salonem. Tento dokument popisuje **technickou realitu systému**.

---

## 3. Kategorie osobních údajů

### 3.1 Zákazníci (`Zakaznik`)

| Údaj | Povinný | Účel |
|------|---------|------|
| Přezdívka / jméno | ano | Identifikace rezervace, zobrazení v kalendáři |
| E-mail | ano (rezervace / registrace) | Potvrzení, připomínky, děkovný e-mail, přihlášení |
| Hash e-mailu (SHA-256) | odvozený | Propojení záznamů po anonymizaci, NO-show bez plaintext e-mailu |
| Heslo (bcrypt hash) | volitelné | Přihlášení do „Moje rezervace“ |
| Potvrzení seznámení se zásadami + datum | ano při registraci / rezervaci | Důkaz splnění informační povinnosti |
| Verze zásad + jazyk + IP | při potvrzení | Evidence v `SouhlasGDPR` a na `Zakaznik` |
| Marketing souhlas | pole existuje, **výchozí false** | **Nepoužíváno** — marketingové e-maily se neodesílají; právní základ by byl čl. 6 odst. 1 písm. a) |
| Blokace účtu | systémové | Po opakovaném NO-show nebo ručně majitelkou |
| Počet NO-show | systémové | Reputace v rámci salonu |

### 3.2 Rezervace (`Rezervace`)

| Údaj | Účel |
|------|------|
| Termín (začátek, konec) | Provoz rezervací |
| Služby, pracovník | Plánování kapacity |
| Poznámka zákazníka | Provozní informace pro salon |
| Interní poznámka | Pouze personál salonu |
| E-mail / jméno hosta | Rezervace bez registrace (`email_host`, `jmeno_host`) |
| Tokeny (UUID) | Storno (`cancel_token`), potvrzení e-mailem (`potvrzeni_token`) |
| Stav rezervace | Provoz, statistiky |
| Časová razítka životního cyklu | `thank_you_sent_at`, `anonymized_at`, `deleted_at` |

### 3.3 Zaměstnanci (`Zamestnanec`)

| Údaj | Účel |
|------|------|
| Jméno, specializace, popis, fotka | Web salonu, kalendář |
| Přihlašovací jméno | Přístup do administrace |
| Heslo (hash) | Autentizace personálu |
| Role (`majitel` / `zamestnanec`) | Řízení přístupu |
| Aktivní (`aktivni`) | Přijímání rezervací + možnost přihlášení |
| Číslo účtu | QR platby u rezervací zaměstnance |

### 3.4 NO-show archiv (`NoShowZaznam`)

| Údaj | Účel |
|------|------|
| Jméno, e-mail (do anonymizace) | Evidence nedorazivších zákazníků **v rámci jednoho salonu** |
| Hash e-mailu | Identifikace po vymazání plaintext e-mailu |
| Metadata rezervace | Audit a rozhodnutí o blokaci |

### 3.5 Audit log (`SalonAuditLog`)

| Údaj | Účel |
|------|------|
| Kdo (`kdo`) | Jméno přihlášeného zaměstnance / majitelky |
| Kdy, kategorie, popis | Sledovatelnost změn |
| Snapshot před/po (JSON) | Detail změny — **hesla a tokeny jsou maskována** (`***`) |

### 3.6 Co systém **nezpracovává**

- Marketingové kampaně ani profilování pro reklamu.
- Platební karty (jen text/QR instrukce a číslo účtu zaměstnance).
- Rodné číslo, zdravotní údaje, citlivé kategorie dle čl. 9 GDPR.

---

## 4. Právní základ zpracování a informační povinnost

### 4.1 Právní základ (čl. 6 GDPR)

Zpracování osobních údajů při online rezervaci a provozu účtu zákazníka probíhá na základě:

**čl. 6 odst. 1 písm. b) GDPR** — zpracování je nezbytné pro **plnění smlouvy** (rezervace služby salonu) nebo pro **provedení opatření před uzavřením smlouvy** na žádost subjektu údajů.

> **Důležité:** Nejde o **souhlas** dle čl. 6 odst. 1 písm. a) GDPR. Checkbox u rezervace proto **není souhlasem se zpracováním** — slouží k **potvrzení seznámení se Zásadami ochrany osobních údajů** (splnění informační povinnosti dle čl. 12–14 GDPR).

### 4.2 Potvrzení informační povinnosti (zákazník)

| Akce | Požadavek |
|------|-----------|
| Nová online rezervace | Povinné **potvrzení seznámení** se [Zásadami ochrany osobních údajů](salon1/ochrana-osobnich-udaju.html) — checkbox ve formuláři; validace na frontendu i v API (technické pole `ochrana_udaju_souhlas`) |
| Registrace účtu zákazníka | Stejné potvrzení seznámení se zásadami |
| Marketing | **Žádný checkbox** — pole `marketing_souhlas` zůstává `false`; marketing se neprovádí |

Text checkboxu ve formuláři: *„Beru na vědomí zpracování osobních údajů podle Zásad ochrany osobních údajů.“*

### 4.3 Evidence potvrzení seznámení (auditní stopa)

Při každém potvrzení seznámení se zásadami (rezervace nebo registrace) systém ukládá důkazní záznam:

| Pole | Popis |
|------|-------|
| `datum` / `cas` | Časové razítko (`SouhlasGDPR.vytvoreno`, `Zakaznik.gdpr_datum`) |
| `ip_adresa` | IP klienta (`SouhlasGDPR.ip_adresa`, `Zakaznik.gdpr_ip`) |
| `zasady_verze` | Verze zásad, se kterými se zákazník seznámil (např. `1.1`) |
| `jazyk` | Jazyk zásad (výchozí `cs`) |
| `zdroj` | `rezervace` / `registrace` |

Verze zásad je konfigurovatelná per salon (`RezervacniNastaveni.gdpr_zasady_verze`) a vrací se v API `/rezervace/info/` jako `gdpr.zasady_verze`. Frontend ji načte při otevření formuláře a odešle v poli `zasady_verze` spolu s `jazyk` při rezervaci i registraci. Veřejný text zásad uvádí aktuální verzi v `ochrana-osobnich-udaju.html` (aktuálně **1.1**). Při každé změně textu majitelka zvýší verzi v nastavení rezervací.

Služba: `backend/rezervace/services/gdpr_consent.py`, model `SouhlasGDPR` (historický název v kódu — obsahově jde o evidenci potvrzení seznámení, nikoli o souhlas dle čl. 6 odst. 1 písm. a)).

> **Poznámka k názvům polí v kódu:** Pole `gdpr_souhlas`, `ochrana_udaju_souhlas` a model `SouhlasGDPR` jsou technické identifikátory z dřívější verze. V dokumentaci a UI se používá formulace **potvrzení seznámení se zásadami**.

### 4.4 Potvrzení rezervace e-mailem

- Online rezervace se vytvoří ve stavu **„Čeká na potvrzení“**.
- Zákazník obdrží e-mail s odkazem; rezervace je platná až po potvrzení.
- Neopotvrzené rezervace se po uplynutí platnosti odkazu (výchozí **24 h**) automaticky zruší.
- Účel: ověření vlastnictví e-mailové adresy, snížení falešných rezervací.

### 4.5 Veřejný dokument

Každý salon má stránku `ochrana-osobnich-udaju.html` s popisem:

- správce vs. platforma,
- rozsah údajů,
- doby uchování (jednotná retenční politika platformy),
- práva subjektu údajů,
- právní základ zpracování (čl. 6 odst. 1 písm. b)),
- absence marketingu.

---

## 5. Účty a přístupová práva

### 5.1 Typy účtů

| Typ | Autentizace | Session |
|-----|-------------|---------|
| **Zákazník** | E-mail + heslo (volitelné) | Token UUID v `localStorage`, platnost **30 dní** (`ZakaznikSession`) |
| **Zaměstnanec** | Přihlašovací jméno + heslo | HTTP hlavička `X-Staff-Token`, platnost **14 dní** (`ZamestnanecSession`) |
| **Majitelka** | Stejný mechanismus jako zaměstnanec, role `majitel` | Stejně |
| **Legacy admin** | Sdílené heslo `SALON_ADMIN_PASSWORD` (dev / přechodné) | Bez session — heslo v každém požadavku |

Hesla (zákazník i personál) se ukládají pouze jako **hash** (Django `make_password` / bcrypt).

### 5.2 Matice oprávnění — personál salonu

| Funkce | Majitelka | Zaměstnanec | Zákazník |
|--------|-----------|-------------|----------|
| Vlastní kalendář rezervací | vše | jen vlastní | — |
| Statistiky | celý salon | jen vlastní | — |
| Nastavení rezervací | ano | ne | — |
| Správa personálu (kadeřnice) | ano | ne | — |
| NO-show archiv, blokace e-mailů | ano | ne | — |
| Audit log | ano | ne | — |
| GDPR export / výmaz zákazníka | ano | ne | — |
| Úprava webu salonu (⚙) | ano | ne | — |
| Nová rezervace (zákaznický formulář) | — | — | ano |
| Moje rezervace / storno odkazem | — | — | ano (vlastní) |

Implementace: `backend/rezervace/services/staff_auth.py`, `backend/salons/permissions.py`.

### 5.3 Deaktivace účtu zaměstnance (bez smazání)

Při odchodu zaměstnance majitelka **deaktivuje účet** — účet se **nemazá**.

| Efekt | Chování |
|-------|---------|
| `aktivni = false` | Zaměstnanec se **nemůže přihlásit** |
| `zobrazit_na_webu = false` | Zmizí z veřejného webu |
| Sessiony | Okamžitě invalidovány |
| Historie rezervací | **Zachována** (vazba na `zamestnanec_id`) |
| Audit log | **Zachován** (jméno v poli `kdo`) |
| Účet majitelky | **Nelze deaktivovat** |

Obnovení: majitelka zaškrtne „Aktivní“ a uloží.

API: `POST /api/salon/<id>/rezervace/admin/zamestnanci/<id>/deaktivovat/`  
(`DELETE` na stejném URL provádí deaktivaci, nikoli fyzické smazání.)

### 5.4 Blokace zákazníka (NO-show)

- NO-show se eviduje **pouze v rámci daného salonu** (`email_reputace.py`).
- Od **2× NO-show**: označení jako problematický.
- Od **3× NO-show**: automatická blokace nových rezervací v tom salonu.
- Majitelka může e-mail ručně zablokovat / odblokovat.
- Blokovaný zákazník při pokusu o rezervaci obdrží: *„Váš účet je blokován. Kontaktujte salon.“*

### 5.5 Administrátorské GDPR nástroje (jen majitelka)

V administraci rezervací → **Nastavení** (pouze role `majitel`):

| Funkce | Popis |
|--------|-------|
| Verze Zásad ochrany osobních údajů | Pole `gdpr_zasady_verze` — musí odpovídat verzi v `ochrana-osobnich-udaju.html` |
| Export údajů subjektu | Vyhledání podle e-mailu → stažení JSON (`GET /api/salon/<id>/rezervace/admin/gdpr/export/?email=...`) |
| Výmaz na žádost | Potvrzení → anonymizace / výmaz osobních údajů (`POST /api/salon/<id>/rezervace/admin/gdpr/vymaz/`) |

Export obsahuje profil zákazníka, rezervace a evidenci potvrzení seznámení se zásadami. Výmaz zachová anonymizované rezervace pro statistiky do konce retention období. Obě operace se zapisují do GDPR audit logu (kap. 8.3).

---

## 6. Životní cyklus osobních údajů rezervace

Automatizovaný cron (doporučeno **každou hodinu**):

```bash
python manage.py rezervace_zivotni_cyklus
```

### 6.1 Časová osa (po ukončení služby)

| Fáze | Čas od konce služby | Co se stane |
|------|---------------------|-------------|
| Provoz | 0 | Salon vidí e-mail zákazníka (platby, NO-show) |
| Děkovný e-mail | +2 h (pokud zapnutý) | Odeslání, `thank_you_sent_at` |
| **Anonymizace** | +24 h | E-mail u salonu smazán, poznámka zákazníka vymazána, `anonymized_at` |
| Soft delete | +12 měsíců od konce služby | `deleted_at` — zmizí z kalendáře salonu |
| Fyzické smazání | po uplynutí retenční doby | Smazání rezervace, historie, souvisejícího audit logu |

### 6.2 Retenční doba (platforma)

Platforma Ulov Rezervaci používá **jednotnou retenční dobu 12 měsíců** pro všechny salony. Tato hodnota je stanovena provozovatelem platformy jako součást bezpečnostních a organizačních opatření a **není uživatelsky měnitelná** (salon ji nemůže změnit v administraci).

Technicky: konstanta `GDPR_UCHOVAVANI_MESICU_DEFAULT` v `backend/salon_api/settings.py` (proměnná prostředí `GDPR_UCHOVAVANI_MESICU`, výchozí `12`). Cron `rezervace_zivotni_cyklus` ji aplikuje stejně na všechny tenanty.

### 6.3 Co anonymizace konkrétně provede

(`backend/rezervace/services/gdpr.py`)

- Vymaže `email_host`, `poznamka_zakaznika` na rezervaci.
- U zákazníka: e-mail nahradí placeholderem `anon-{id}@anonym.ulovrezervaci.local`, uloží SHA-256 hash původního e-mailu, smaže heslo a sessiony.
- U NO-show záznamů: vymaže plaintext e-mail, ponechá hash.
- V historii rezervace vyčistí e-mailové údaje ze snapshotů.

### 6.4 Co po anonymizaci zůstává

- Přezdívka / jméno u rezervace.
- Termín, služby, pracovník, stav.
- Agregované statistiky salonu (bez identifikace e-mailu).

### 6.5 Neopotvrzené online rezervace

- Stav `ceka` + expirace potvrzovacího odkazu (výchozí 24 h).
- Po expiraci: automatické zrušení (`zakaznik_storno`), uvolnění termínu.

---

## 7. E-mailová komunikace

| Typ e-mailu | Příjemce | Kdy | Marketing |
|-------------|----------|-----|-----------|
| Výzva k potvrzení rezervace | zákazník | Po vytvoření online rezervace | ne |
| Potvrzení rezervace | zákazník | Po potvrzení / okamžitě u personálu | ne |
| Připomínka před termínem | zákazník | Dle nastavení (např. +24 h před) | ne |
| Děkovný e-mail / recenze | zákazník | Po službě (např. −2 h od konce) | ne |
| NO-show upozornění | zákazník | Ručně majitelkou | ne |
| Žádost o platbu (QR) | zákazník | Ručně personálem | ne |
| Storno | zákazník (+ kopie salonu) | Při zrušení | ne |
| Zapomenuté heslo | zákazník | Na žádost | ne |

Odesílání: SMTP **per salon** (nastavení v administraci webu) nebo proměnné prostředí.  
Obsah e-mailů: šablony v `backend/rezervace/templates/rezervace/emails/`.

---

## 8. Audit a sledovatelnost

### 8.1 Audit log salonu

- Zapisuje změny: rezervace, personál, nastavení, otevírací doba, e-mail SMTP, …
- Actor = jméno přihlášeného staff (`audit_actor` z `X-Staff-Token`).
- Citlivá pole (`password`, `smtp_password`, `token`, …) se do logu ukládají jako `***`.
- Přístup: **pouze majitelka**.
- Retence: mazání záznamů starších **12 měsíců** (cron).

### 8.2 Historie rezervace (`RezervaceHistorie`)

- Interní log změn konkrétní rezervace (kdo, co, kdy).
- Po fyzickém smazání rezervace se historie také maže.

### 8.3 GDPR audit log

Samostatný log operací souvisejících s ochranou osobních údajů (`backend/rezervace/services/gdpr_audit.py`):

| Operace | Kdo spustil |
|---------|-------------|
| Export osobních údajů zákazníka | Majitelka |
| Výmaz na žádost subjektu | Majitelka |
| Deaktivace / aktivace účtu zaměstnance | Majitelka |

Každý záznam obsahuje čas, IP, popis a identifikaci subjektu (e-mail / ID).

---

## 9. Bezpečnostní opatření (technická)

| Oblast | Implementace |
|--------|--------------|
| Hesla | Hash (Django password hashers), min. délka 6 (personál) / 8 (zákazník registrace) |
| API autentizace personálu | Bearer-like token v hlavičce `X-Staff-Token` |
| Storno / potvrzení bez přihlášení | Jednorázové UUID tokeny v URL |
| Izolace tenantů | Všechny dotazy filtrují `salon_id` |
| Session expiry | Automatické mazání expirovaných session (cron) |
| Deaktivovaný personál | Okamžitá invalidace session + odmítnutí loginu |
| Audit | Maskování citlivých hodnot v JSON snapshotech |
| Rate limiting | `backend/rezervace/throttles.py` — login 5/min, rezervace 20/h, reset hesla 3/h, potvrzení e-mailu 10/h (per IP) |
| Security headers | `backend/salon_api/security_middleware.py` — CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy |
| CORS | `django-cors-headers` — v produkci `CORS_ALLOWED_ORIGINS` z env; hlavička `X-Staff-Token` povolena |
| CSRF | API **nepoužívá session cookies** — autentizace přes tokeny (`X-Staff-Token`, `session_token` v těle / `localStorage`). CSRF útok na cookie-based session proto není primární vektor; storno a potvrzení rezervace chrání jednorázové UUID tokeny v URL |

### 9.1 Rate limiting (per IP)

Ochrana proti zneužití citlivých endpointů (`backend/rezervace/throttles.py`, cache v `settings.py`):

| Endpoint | Limit |
|----------|-------|
| Login zákazníka | 5 / minuta |
| Login personálu | 5 / minuta |
| Nová rezervace (`POST /rezervace/`) | 20 / hodina |
| Reset hesla | 3 / hodina |
| Potvrzení rezervace e-mailem | 10 / hodina |

Při překročení limitu API vrací HTTP **429 Too Many Requests**.

### 9.2 CORS a security headers

- **CORS:** `django-cors-headers`; v produkci nastavit proměnnou `CORS_ALLOWED_ORIGINS` (seznam povolených domén frontendu).
- **Security headers** (`backend/salon_api/security_middleware.py`): `Content-Security-Policy`, `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`. V produkci s HTTPS doplnit `SECURE_*` nastavení Django.

### 9.3 Doporučení před produkcí

| Oblast | Aktuální stav | Doporučení |
|--------|---------------|------------|
| Přenos | HTTP v dev | **HTTPS povinně**, HSTS (middleware připraveno pro `SECURE_*`) |
| Legacy heslo | `SALON_ADMIN_PASSWORD` pro celou instanci | Odstranit v produkci, pouze staff tokeny |
| Databáze | SQLite v dev | PostgreSQL, šifrované zálohy |
| Rate limiting | Implementováno (in-memory cache) | V produkci Redis pro sdílený limit mezi workers |
| Logování přístupů | Audit změn + GDPR audit | Centrální logy serveru |
| DPA se subdodavateli | Bunny.net (obrázky), SMTP poskytovatel | Smluvní pokrytí |

Detail: `TECHNICKE_NASAZENI.md`, sekce 8.

---

## 10. Práva subjektů údajů (čl. 12–22 GDPR)

| Právo | Jak je v systému podporováno |
|-------|------------------------------|
| **Informace** | `ochrana-osobnich-udaju.html` + potvrzení seznámení se zásadami při rezervaci |
| **Přístup** | Zákazník: „Moje rezervace“ po přihlášení; jinak žádost na salon / platformu |
| **Oprava** | Zákazník může zadat nové jméno při další rezervaci; majitelka může upravit v adminu |
| **Výmaz** | Automatický po 12 měsících (platforma); předčasný výmaz — majitelka v adminu (GDPR → Výmaz na žádost) |
| **Omezení** | Blokace účtu (`blokovan`) |
| **Přenositelnost** | Export .ics jedné rezervace; **hromadný export JSON** — majitelka (`GET .../admin/gdpr/export/`) |
| **Námitka proti marketingu** | Není relevantní — marketing se neprovádí |
| **Stížnost u ÚOOÚ** | Informováno v zásadách ochrany osobních údajů |

> **Provozní poznámka:** Pro plnou compliance je nutné definovat **proces vyřizování žádostí** (kontaktní e-mail, lhůty 30 dní) na straně salonu a platformy.

---

## 11. Subdodavatelé a přenos dat

| Subdodavatel | Účel | Osobní údaje |
|--------------|------|--------------|
| **SMTP poskytovatel salonu** (např. Forpsi) | Odesílání transakčních e-mailů | E-mail zákazníka, jméno v těle zprávy |
| **Bunny.net** (volitelně) | CDN / úložiště obrázků webu | Fotky personálu (jméno v alt textu na webu), ne zákaznické údaje |
| **Hosting API / DB** | Provoz platformy | Všechna data dle této dokumentace |

Data **nejsou** prodávána třetím stranám ani používána pro reklamu.

---

## 12. Přehled klíčových souborů (pro audit kódu)

| Oblast | Soubor |
|--------|--------|
| GDPR anonymizace | `backend/rezervace/services/gdpr.py` |
| Evidence potvrzení seznámení | `backend/rezervace/services/gdpr_consent.py` |
| Admin export / výmaz | `backend/rezervace/services/gdpr_admin.py` |
| GDPR audit | `backend/rezervace/services/gdpr_audit.py` |
| Rate limiting | `backend/rezervace/throttles.py` |
| Security headers | `backend/salon_api/security_middleware.py` |
| Životní cyklus | `backend/rezervace/services/zivotni_cyklus.py` |
| NO-show / blokace | `backend/rezervace/services/email_reputace.py` |
| Přihlášení personálu | `backend/rezervace/services/staff_auth.py` |
| Oprávnění API | `backend/salons/permissions.py` |
| Audit | `backend/rezervace/services/audit.py` |
| Modely | `backend/rezervace/models.py` |
| Zásady pro zákazníky | `salon1/ochrana-osobnich-udaju.html`, `salon2/ochrana-osobnich-udaju.html` |
| Cron příkaz | `backend/rezervace/management/commands/rezervace_zivotni_cyklus.py` |

---

## 13. Shrnutí pro compliance officer

### Co systém dělá správně

1. **Minimizace údajů** — žádný marketing, žádné citlivé kategorie.
2. **Izolace salonů** — žádné sdílení zákazníků ani NO-show mezi tenanty.
3. **Automatická anonymizace** e-mailů u salonu do 24 h po službě.
4. **Automatické mazání** po 12 měsících (jednotná retenční politika platformy) včetně audit logu starších záznamů.
5. **Oddělené účty personálu** s rolemi majitel / zaměstnanec.
6. **Deaktivace bez smazání** — zachování auditu a historie.
7. **Dokumentované potvrzení seznámení** se zásadami — včetně data, času, IP, verze a jazyka (právní základ čl. 6 odst. 1 písm. b), nikoli souhlas).
8. **Potvrzení rezervace e-mailem** — ověření e-mailové adresy.
9. **Audit log** s maskováním hesel.
10. **Rate limiting** citlivých endpointů.
11. **Security headers** a CORS.
12. **Admin export a výmaz** osobních údajů na žádost.
13. **GDPR audit log** exportů, výmazů a změn účtů personálu.
14. **Jednotná retenční doba 12 měsíců** — stanovena provozovatelem platformy, salony ji nemohou měnit.

### Co vyžaduje doplnění mimo software

1. Smlouva DPA mezi platformou a salony.
2. Záznamy o činnostech zpracování (ROPA) per správce.
3. Proces vyřizování žádostí subjektů údajů.
4. Produkční hardening (HTTPS, odstranění legacy hesla, zálohy).
5. Posouzení DPIA (doporučeno při větším rozsahu nebo citlivějších údajích).

---

## 14. Historie verzí dokumentu

| Verze | Datum | Změna |
|-------|-------|-------|
| 1.0 | červenec 2026 | První vydání — GDPR, účty, přístupy, životní cyklus, audit, deaktivace personálu |
| 1.1 | červenec 2026 | Evidence potvrzení seznámení (IP, verze, jazyk), rate limiting, security headers, admin GDPR export/výmaz |
| 1.2 | červenec 2026 | Terminologie: právní základ čl. 6 odst. 1 písm. b) místo „souhlasu“; doplněny tabulky rate limiting, admin GDPR nástroje, CSRF/CORS |
| 1.3 | červenec 2026 | Retenční doba sjednocena na 12 měsíců na úrovni platformy — salony ji nemohou měnit |

---

*Tento dokument popisuje stav kódu platformy Ulov Rezervaci k datu vydání. Nepředstavuje právní poradenství; finální compliance posouzení má provést právník / DPO v kontextu konkrétního nasazení.*
