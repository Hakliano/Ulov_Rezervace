# For Compliance — popis funkcí a zpracování údajů

**Systém / produkt:** Ulov Rezervaci (značka **ULOV KLIENTY**)  
**Verze dokumentu:** 1.5  
**Datum:** srpen 2026  
**Určeno pro:** právní oddělení, DPO, compliance — podklad k DPA, ROPA, zásadám, **partnerským smlouvám**  
**Stav produktu:** ostrý provoz (LIVE) + staging; PostgreSQL, HTTPS, Docker na Hetzner VPS

---

## 0. Povinná sada dokumentů pro právní

| Dokument | Co obsahuje |
|----------|-------------|
| **`PODKLAD_PRO_PARTNERY.md`** | **Obchodní nabídka** (3 balíčky, ceny, vstupní poplatky), **všechny služby**, **kompletní FLOW** (majitel + pracovník), matice balíčků |
| **Tento dokument (`For Compliance v1.md`)** | GDPR, kategorie údajů, role, retence, bezpečnost, práva subjektů |
| **`dokumenty/`** | Formální DPA, přílohy, ROPA (HTML/PDF) |

Bez `PODKLAD_PRO_PARTNERY.md` nelze správně sepsat ceník závazků Partnerství ani popis FLOW ve smlouvě.

---

## 1. Účel dokumentu

Tento dokument popisuje **co platforma dělá (funkční rozsah)** a **jak zpracovává osobní údaje** — účty, přístupová práva, životní cyklus dat, e-maily, subdodavatele a technické kontroly.

Slouží jako podklad pro:

- smlouvu o zpracování osobních údajů (DPA) mezi provozovatelem platformy a partnerem (provozovnou),
- ROPA a přílohy DPA,
- zásady ochrany osobních údajů pro zákazníky partnera,
- interní audit / odpověď ÚOOÚ.

| Související materiál | Obsah |
|----------------------|--------|
| **`PODKLAD_PRO_PARTNERY.md`** | Ceník, 3 balíčky, vstupní poplatky, Program růstu, **FLOW detail majitel/pracovník** |
| `dokumenty/` (HTML/PDF) | DPA, přílohy 1–3, ROPA — formální verze pro partnery |
| `ZIVOTNI_CYKLUS_REZERVACE.md` | Detail retenčních lhůt a cronu |
| `TECHNICKE_NASAZENI.md` | Technická architektura |
| `PREHLED_PRO_SALES_A_MARKETING.md` | Obchodní popis (není compliance podklad) |
| `salon*/ochrana-osobnich-udaju.html` | Veřejný text pro zákazníky dané provozovny |

> Dokument popisuje **technickou realitu systému** (zejm. GDPR). Obchodní závazky a FLOW → **`PODKLAD_PRO_PARTNERY.md`**. Finální právní kvalifikace náleží právnímu oddělení.

---

## 1a. Obchodní nabídka (stručný odkaz)

Veřejný ceník (stav srpen 2026) — **plný text v `PODKLAD_PRO_PARTNERY.md`**:

| Balíček | Cena | Vstupní nastavení |
|---------|------|-------------------|
| Web jednorázově | 4 000 Kč jednorázově | — |
| Partnerský web | 199 Kč/měs. (běžně 299); akce do 31. 12. 2026 navždy | — |
| Partner pro provozovnu | 499 Kč/měs. (běžně 799); akce do 31. 12. 2026 navždy | **2 999 Kč** standard / **3 999 Kč** vč. Programu růstu |

Měsíční Partnerství zahrnuje WEB + rezervace + FLOW + podporu; Program růstu jen při vstupu 3 999 Kč.

---

## 1b. FLOW (stručný odkaz)

FLOW = provozní CRM na `https://www.ulovklienty.cz/flow/`.

- **Majitel:** Správa (pravidla, šablony, personál/FLOW přístupy, volno, platby ULOV, NO-show, audit, statistiky) + denní provoz rezervací.  
- **Pracovník:** vlastní kalendář, žádosti o volno, změna hesla, volitelně overview a Mail.  
- **Mimo FLOW:** obsah webu, ceník, SMTP/IMAP credentials, heslo majitele → web ⚙.

**Kompletní inventář akcí** → kapitola 6 v `PODKLAD_PRO_PARTNERY.md`.

---

## 2. Stručný popis produktu

**ULOV KLIENTY** poskytuje partnerovi (salon, ordinace, řemeslo, provozovna):

1. **Veřejný web** provozovny (obsah, fotky, ceník, kontakt),
2. **Online rezervace** pro zákazníky (včetně e-mailových potvrzení a storna),
3. **Administraci webu** (majitel),
4. **FLOW** — pracovní prostředí majitele a personálu (kalendář, provoz, interní komunikace),
5. Volitelně **Program růstu / partnerství** a podporu (mimo rozsah zpracování v tomto dokumentu, pokud nejde o smluvní vztah).

Jeden backend obsluhuje **více partnerů (tenantů)**. Data jsou izolována přes `salon_id`. **Zákaznická data se mezi partnery nesdílejí.**

Veřejné prostředí: `https://www.ulovklienty.cz/` (hub), dema a partner weby, API `https://api.ulovklienty.cz/`.  
Staging (test): `https://www.staging.ulovklienty.cz/` — oddělená databáze; transakční maily lze přesměrovat na testovací schránku.

---

## 3. Inventář funkcí (pro právní mapování)

### 3.1 Prezentační / marketingový hub (`presentace/`)

| Funkce | Popis | Osobní údaje |
|--------|--------|--------------|
| Vertikální landing pages | Beauty, zdraví, řemesla, provozovny — nabídka partnerství | Ne (statický obsah) |
| Formulář **nezávazné poptávky** | Jméno, e-mail, souhlas se zpracováním poptávky | Ano — zájemce o partnerství (`POST /api/poptavka/`) |
| Odkazy na dema | Ukázkové weby a rezervace | Ne |

### 3.2 Veřejný web partnera

| Funkce | Popis | Osobní údaje |
|--------|--------|--------------|
| Úvod / O nás | Název, popis, hero fotka, CTA rezervace | Ne (obsah partnera) |
| Galerie | Fotografie provozovny | Ne (může obsahovat tváře — dle partnera) |
| Personál | Jméno, specializace, popis, fotka, rozvrh | Ano — zaměstnanci zveřejnění partnerem |
| Ceník | Služby a ceny | Ne |
| Novinky | Texty + volitelné obrázky | Ne |
| Kontakt | Adresa, telefon, e-mail provozovny | Kontaktní údaje partnera (B2B) |
| Zásady ochrany osobních údajů | `ochrana-osobnich-udaju.html` | Informační text |

### 3.3 Online rezervace (zákazník)

| Funkce | Popis | Osobní údaje |
|--------|--------|--------------|
| Nová rezervace | Služby, personál, termín, jméno, e-mail, poznámka | Ano |
| Potvrzení e-mailem | Odkaz s tokenem; neopotvrzené se zruší (výchozí 24 h) | Ano (e-mail + token) |
| Storno odkazem | UUID token v e-mailu, bez přihlášení | Ano (token) |
| Registrace / přihlášení zákazníka | Účet „Moje rezervace“ | Ano |
| Zapomenuté heslo | Nové heslo e-mailem | Ano |
| Export do kalendáře (.ics) | Jedna rezervace | Termín + služba |
| Potvrzení seznámení se zásadami | Povinný checkbox (informační povinnost, ne marketingový souhlas) | Evidence (IP, verze, čas) |

### 3.4 Administrace webu (majitel, ⚙ na webu)

| Funkce | Popis | Osobní údaje |
|--------|--------|--------------|
| Úprava textů a kontaktů | Název, popis, adresa, telefon, e-mail | Kontakt partnera |
| Upload obrázků | Hero, galerie, logo — úložiště Bunny.net | Fotky (vč. personálu) |
| Správa ceníku / novinek | Obsah webu | Ne |
| SMTP nastavení | Odesílání transakčních e-mailů jménem partnera | Přihlašovací údaje ke schránce partnera |
| URL stránky rezervací | Odkazy v e-mailech zákazníkům | Konfigurace |
| Správa personálu (zobrazení na webu) | Jméno, foto, rozvrh | Ano |
| Aktivace / vstup do FLOW | Stejný e-mail a heslo majitele | Ano |
| Změna hesla majitele | Sdílené heslo web + FLOW | Hash hesla |

### 3.5 FLOW — provozní prostředí týmu (`/flow/`)

Denní provoz personálu (kalendář, směny, interní práce) probíhá ve **FLOW**, nikoli na veřejné stránce rezervací.

| Funkce | Popis | Osobní údaje |
|--------|--------|--------------|
| Přihlášení | E-mail + heslo (`FlowUser` vázaný na zaměstnance / majitele) | Ano |
| Kalendář rezervací | Provozní přehled, stavy (dokončeno, storno, …) | Ano — zákazníci rezervací |
| Absence / volno | Plánování dostupnosti personálu | Ano — zaměstnanci |
| Interní oznámení / banner | Zprávy pro tým po přihlášení | Text (provozní) |
| FLOW Mail (volitelně) | Čtení / odesílání firemní schránky přes IMAP/SMTP partnera | Ano — obsah e-mailů ve schránce partnera |
| Aktivace přístupu | Majitel vytvoří / resetuje přístup zaměstnance; dočasné heslo | Ano |
| Blokace přístupu | Zakázání přihlášení do FLOW | Ano |

### 3.6 Partner-admin (interní ops platformy)

Interní rozhraní provozovatele platformy pro správu partnerů (domény, přístupy, platby partnerství — dle nasazení). **Není určeno zákazníkům salonů.** Může zobrazovat provozní údaje partnera a stavy FLOW.

### 3.7 Automatizace na pozadí (cron / Celery)

| Proces | Účel |
|--------|------|
| Připomínky před termínem | Transakční e-mail zákazníkovi |
| Děkovný e-mail / výzva k recenzi | Transakční e-mail po službě (URL recenze nastaví partner) |
| Expirace neopotvrzených rezervací | Uvolnění termínu |
| Anonymizace (24 h po službě) | Smazání e-mailu / poznámky u salonu |
| Soft delete / fyzické mazání | Retence 12 měsíců |
| Mazání starého audit logu | Retence 12 měsíců |

---

## 4. Architektura a role v GDPR

### 4.1 Multi-tenant model

- Jeden backend, více salonů / provozoven (`Salon` + `salon_id`).
- **Data mezi partnery se nesdílejí** (zákazníci, NO-show, blokace e-mailů).
- Každý partner: vlastní obsah webu, SMTP, branding, personál, rezervace.

### 4.2 Role správce vs. zpracovatele (technický pohled)

| Role | Kdo | Odpovědnost (fakticky v systému) |
|------|-----|----------------------------------|
| **Správce** (vůči zákazníkovi provozovny) | Partner (majitel provozovny) | Účel rezervací, komunikace se zákazníkem, obsah webu, SMTP, personál |
| **Zpracovatel** | Provozovatel platformy Ulov Rezervaci | Hosting API/DB, automatický životní cyklus, infrastruktura |
| **Subjekt údajů** | Zákazník provozovny | Osoba rezervující termín |
| **Uživatel s oprávněním** | Majitel, zaměstnanec | Web admin / FLOW |
| **Zájemce o partnerství** | Osoba z poptávkového formuláře | B2B lead — oddělený účel od rezervací |

> Finální smluvní vymezení správce/zpracovatele potvrdí právní oddělení ve DPA.

---

## 5. Kategorie osobních údajů

### 5.1 Zákazníci (`Zakaznik`)

| Údaj | Povinný | Účel |
|------|---------|------|
| Přezdívka / jméno | ano | Identifikace rezervace, kalendář |
| E-mail | ano (rezervace / registrace) | Potvrzení, připomínky, děkovný mail, přihlášení |
| Hash e-mailu (SHA-256) | odvozený | Propojení po anonymizaci, NO-show |
| Heslo (hash) | volitelné | „Moje rezervace“ |
| Potvrzení seznámení se zásadami + datum | ano při rezervaci / registraci | Informační povinnost |
| Verze zásad + jazyk + IP | při potvrzení | Evidence (`SouhlasGDPR` / pole na zákazníkovi) |
| Marketing souhlas | pole existuje, **výchozí false** | **Nepoužíváno** — marketingové kampaně se neodesílají |
| Blokace účtu, počet NO-show | systémové | Ochrana provozu v rámci jedné provozovny |

### 5.2 Rezervace (`Rezervace`)

| Údaj | Účel |
|------|------|
| Termín, služby, pracovník | Provoz |
| Poznámka zákazníka / interní poznámka | Provoz |
| E-mail / jméno hosta (bez účtu) | Rezervace bez registrace |
| Tokeny UUID | Storno, potvrzení e-mailem |
| Stav, časová razítka životního cyklu | Provoz, GDPR |

### 5.3 Zaměstnanci a FLOW (`Zamestnanec`, `FlowUser`)

| Údaj | Účel |
|------|------|
| Jméno, specializace, popis, fotka | Web, kalendář |
| Přihlašovací e-mail / jméno | Autentizace web + FLOW |
| Heslo (hash) | Autentizace |
| Role (`majitel` / `zamestnanec`) | Oprávnění |
| Číslo účtu (volitelně) | QR platby (SPAYD) — účet **zaměstnance/partnera**, ne karty zákazníků |
| FLOW session token | Přihlášení do FLOW |
| IMAP/SMTP credentials provozovny | FLOW Mail — přístup ke schránce partnera |

### 5.4 NO-show archiv, audit

- NO-show: jméno/e-mail (do anonymizace), hash, metadata — **jen v rámci jedné provozovny**.
- Audit log: kdo, kdy, co; hesla/tokeny maskovány (`***`).
- GDPR audit: export / výmaz / změny účtů personálu.

### 5.5 Poptávka z hubu

| Údaj | Účel |
|------|------|
| Jméno, e-mail, zpráva (dle formuláře) | Vyřízení B2B poptávky partnerství |
| Souhlas / potvrzení dle formuláře | Evidence u leadu |

### 5.6 Co systém **nezpracovává** (běžně)

- Marketingové kampaně a profilování pro reklamu.
- Platební karty zákazníků (jen QR / textové platební instrukce).
- Rodné číslo, občanský průkaz, zdravotní údaje, zvláštní kategorie dle čl. 9 GDPR.
- Telefon a adresa bydliště **zákazníka** (není součástí standardního rezervačního formuláře).

---

## 6. Právní základ a informační povinnost (zákazník provozovny)

### 6.1 Právní základ

**čl. 6 odst. 1 písm. b) GDPR** — plnění smlouvy / opatření před uzavřením smlouvy (rezervace služby).

Checkbox u rezervace **není souhlasem** dle čl. 6 odst. 1 písm. a) — jde o **potvrzení seznámení se Zásadami** (čl. 12–14 GDPR).

### 6.2 Evidence seznámení

Ukládá se čas, IP, verze zásad, jazyk, zdroj (`rezervace` / `registrace`).  
Technické názvy polí (`SouhlasGDPR`, `ochrana_udaju_souhlas`) jsou historické — obsahově jde o evidenci seznámení.

### 6.3 Potvrzení rezervace e-mailem

Online rezervace vzniká ve stavu „čeká na potvrzení“; platnost odkazu výchozí **24 h**, pak automatické zrušení. Účel: ověření e-mailu, snížení falešných rezervací.

---

## 7. Účty a přístupová práva

### 7.1 Typy účtů

| Typ | Autentizace | Session |
|-----|-------------|---------|
| Zákazník | E-mail + heslo (volitelné) | Token UUID, cca 30 dní |
| Zaměstnanec | E-mail / login + heslo | `X-Staff-Token`, cca 14 dní; FLOW session |
| Majitel | Stejně, role `majitel` | Web admin + FLOW |
| Legacy admin heslo | `SALON_ADMIN_PASSWORD` (dev / přechodné) | Bez session — **není cíl produkčního modelu** |

Hesla pouze jako hash (Django password hashers).

### 7.2 Matice oprávnění (zjednodušeně)

| Funkce | Majitel | Zaměstnanec | Zákazník |
|--------|---------|-------------|---------|
| Úprava webu (⚙) | ano | ne | — |
| Nastavení rezervací, GDPR export/výmaz | ano | ne | — |
| Správa personálu / FLOW účtů | ano | ne | — |
| Kalendář / provoz ve FLOW | ano (celý) | ano (dle oprávnění / vlastní) | — |
| Nová rezervace / moje rezervace | — | — | ano |

### 7.3 Deaktivace zaměstnance

Účet se **nemaže** — `aktivni = false`, invalidace session, historie rezervací a audit zůstávají. Účet majitele nelze deaktivovat stejnou cestou.

### 7.4 Blokace zákazníka (NO-show)

Jen v rámci provozovny: od 2× problematický, od 3× auto-blokace online rezervací; majitel může blokovat ručně.

### 7.5 GDPR nástroje majitele

Export JSON podle e-mailu; výmaz na žádost (anonymizace se zachováním anonymních statistik do konce retence). Obě operace do GDPR audit logu.

---

## 8. Životní cyklus osobních údajů rezervace

Cron: `python manage.py rezervace_zivotni_cyklus` (doporučeno hodinově).

| Fáze | Čas od konce služby | Akce |
|------|---------------------|------|
| Provoz | 0 | Partner vidí e-mail (platby, NO-show) |
| Děkovný e-mail | +2 h (pokud zapnutý) | Odeslání |
| **Anonymizace** | **+24 h** | E-mail a poznámka zákazníka pryč |
| Soft delete | +12 měsíců | Zmizí z běžného kalendáře |
| Fyzické smazání | po retenci | Smazání včetně související historie |

**Retence platformy: 12 měsíců** — jednotná, partner ji v administraci **nemění** (`GDPR_UCHOVAVANI_MESICU`).

Detail: `ZIVOTNI_CYKLUS_REZERVACE.md`.

---

## 9. E-mailová komunikace (transakční)

| Typ | Příjemce | Marketing |
|-----|----------|-----------|
| Výzva k potvrzení rezervace | zákazník | ne |
| Potvrzení / připomínka / storno | zákazník (+ storno kopie partnerovi) | ne |
| Děkovný / výzva k recenzi | zákazník | ne (odkaz na recenze partnera) |
| NO-show / QR platba | zákazník | ne |
| Zapomenuté heslo | zákazník | ne |
| FLOW přístup (dočasné heslo) | zaměstnanec / majitel | ne |
| Poptávka partnerství | provozovatel platformy | B2B lead |

Odesílání: **SMTP nastavené partnerem** (nebo env). Odkazy v mailech používají `web_rezervace_url` partnera (absolutní HTTPS URL produkční stránky rezervací).  
Volitelně fronta Celery + Redis.

**FLOW Mail:** při zapnutí IMAP čte systém schránku partnera — obsah e-mailů zpracovává jménem partnera jako součást poskytované funkce.

---

## 10. Audit a sledovatelnost

- Audit log změn (rezervace, personál, nastavení, SMTP…) — citlivá pole maskována.
- Historie jednotlivých rezervací.
- GDPR audit (export, výmaz, deaktivace účtů).
- Retence auditních záznamů: typicky 12 měsíců (cron).

---

## 11. Bezpečnostní opatření (technická)

| Oblast | Stav |
|--------|------|
| Hesla | Hash |
| API personálu | Token hlavička / FLOW session |
| Storno / potvrzení | Jednorázové UUID v URL |
| Izolace tenantů | Filtr `salon_id` |
| Rate limiting | Login, rezervace, reset hesla, potvrzení (per IP) |
| Security headers | CSP, X-Frame-Options, … |
| CORS | Povolené produkční origins |
| Přenos | HTTPS (LIVE) |
| DB | PostgreSQL (LIVE/staging); SQLite jen lokální vývoj |
| Hosting | Hetzner VPS, Docker Compose |
| Média | Bunny.net (cesta `webs/salon-{id}/…`) |
| Zálohy | DB + konfigurace + `www/` (cron / před deployem) |

---

## 12. Práva subjektů údajů (čl. 12–22)

| Právo | Podpora v systému |
|-------|-------------------|
| Informace | Zásady na webu + checkbox seznámení |
| Přístup | Moje rezervace; export majitelem |
| Oprava | Nová rezervace / úprava v adminu |
| Výmaz | Auto po 12 měs.; předčasně majitel (GDPR výmaz) |
| Přenositelnost | .ics; JSON export majitelem |
| Námitka marketingu | Není relevantní — marketing se neprovádí |
| Stížnost ÚOOÚ | Uvedeno v zásadách |

Provozní lhůty a kontaktní proces (30 dní) musí doplnit smlouva / interní postup partnera a platformy.

---

## 13. Subdodavatelé (orientační)

| Subdodavatel | Účel | Osobní údaje |
|--------------|------|--------------|
| **Hetzner** | Hosting VPS (API, DB, staging) | Data dle této dokumentace |
| **Bunny.net** | CDN / storage obrázků webu | Fotky webu / personálu (ne rezervační e-maily zákazníků) |
| **SMTP poskytovatel partnera** (např. Forpsi) | Transakční maily | E-mail a jméno v těle zprávy |
| **IMAP** (stejná schránka partnera) | FLOW Mail | Obsah schránky partnera |

Aktuální smluvní seznam: `dokumenty/priloha-03-dalsi-zpracovatele.html`.  
Data se **neprodávají** třetím stranám ani nepoužívají k reklamě platformy.

---

## 14. Co musí právní / compliance doplnit mimo software

1. Finální texty DPA a příloh (složka `dokumenty/`).
2. ROPA správce (partner) a zpracovatele (platforma).
3. Proces vyřizování žádostí subjektů (kontakt, lhůty).
4. Posouzení DPIA dle rozsahu a rizik.
5. Smluvní pokrytí subdodavatelů a B2B poptávek z hubu.
6. Texty zásad na webech partnerů (verze musí sedět s `gdpr_zasady_verze`).

---

## 15. Klíčové soubory v kódu (pro audit)

| Oblast | Umístění |
|--------|----------|
| GDPR anonymizace / admin | `backend/rezervace/services/gdpr*.py` |
| Životní cyklus | `backend/rezervace/services/zivotni_cyklus.py` |
| NO-show | `backend/rezervace/services/email_reputace.py` |
| E-maily rezervací | `backend/rezervace/services/emails.py` |
| URL rezervací v mailech | `backend/rezervace/services/booking_urls.py` |
| Staff / majitel auth | `backend/rezervace/services/staff_auth.py` |
| FLOW | `backend/flow/` |
| Partner-admin | `backend/partner_admin/` |
| Zásady pro zákazníky | `*/ochrana-osobnich-udaju.html` |
| Formální DPA/ROPA | `dokumenty/` |

---

## 16. Shrnutí pro právní oddělení

### Produkt umí (podstatné pro dokumentaci)

- Multi-tenant web + rezervace + FLOW pro libovolný počet partnerů.
- Transakční e-maily bez marketingu.
- Automatická anonymizace a retence.
- Role majitel / zaměstnanec / zákazník; izolace dat mezi partnery.
- Export a výmaz na žádost (nástroje majitele).
- Evidence seznámení se zásadami (ne marketingový souhlas).

### Produkt záměrně neumí / nedělá

- Sdílení zákazníků mezi provozovnami.
- Marketingové newslettery zákazníkům.
- Zpracování platebních karet.
- Zvláštní kategorie údajů dle čl. 9.

---

## 17. Historie verzí

| Verze | Datum | Změna |
|-------|-------|-------|
| 1.0–1.3 | červenec 2026 | GDPR jádro, účty, retence 12 měs., rate limit, admin GDPR |
| 1.4 | srpen 2026 | Inventář funkcí; FLOW; LIVE stack; subdodavatelé |
| **1.5** | **srpen 2026** | Odkaz na `PODKLAD_PRO_PARTNERY.md` (ceny, balíčky, vstupní poplatky, kompletní FLOW); sekce 0 / 1a / 1b |

---

*Dokument popisuje stav platformy Ulov Rezervaci / ULOV KLIENTY k datu vydání. Nepředstavuje právní poradenství; finální compliance posouzení provádí právní oddělení / DPO.*
