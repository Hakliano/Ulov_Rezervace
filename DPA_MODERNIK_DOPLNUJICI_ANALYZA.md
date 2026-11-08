# Doplňující technická analýza GDPR / MODERNÍK

| Položka | Hodnota |
|--------|---------|
| Navazuje na | `DPA_MODERNIK_TECHNICKY_AUDIT.md` (F1–F36) |
| Datum | 25. 10. 2026 |
| Typ | Analýza only — **bez** změn kódu, DB, DPA, STAGING/LIVE deploye |
| LIVE kontrola | Read-only (stav Sentry = ano/ne, retence záloh; **bez** čtení OÚ a bez výpisu tajemství) |

Legenda typu zjištění: **technická chyba** · **neaktuální text DPA** · **chybějící interní postup** · **bezpečnostní riziko (k ověření)** · **OK / žádný problém**

---

## A. Anonymizace rezervací a Archivník (F6, F8, F14, F17)

### Současný stav — životní cyklus

#### A1. Co zůstává v rezervaci po „24 h od termínu“

Anonymizace **neběží automaticky přesně 24 h po začátku/konci termínu pro každou rezervaci**. Cron `rezervace_zivotni_cyklus` (~1×/h) anonymizuje jen když:

1. `stav ∈ {dokonceno, no_show, zakaznik_storno, salon_storno}`,
2. `now >= konec + 24 h`,
3. u `dokonceno` s aktivním děkovným mailem: existuje `thank_you_sent_at`.

Do té doby (a u stavů `ceka` / `potvrzeno`) zůstává plaintext e-mail viditelný Partnerovi (viz audit F1).

#### A2. Co se maže / co zůstává při anonymizaci rezervace

| Údaj | Po `anonymizuj_obsah_rezervace` |
|------|--------------------------------|
| E-mail (`email_host` / `Zakaznik.email`) | Vymazán / nahrazen `anon-{id}@anonym.ulovrezervaci.local` |
| Poznámka zákazníka | Vymazána |
| Heslo / session zákazníka | Vymazány |
| Marketing souhlas | `False` |
| NO-show plaintext e-mail | Vymazán; **hash zůstává** |
| Historie rezervace — klíče s `email` | Scrubnuty na `''` |
| Jméno hosta (`jmeno_host`) | **Zůstává** |
| Přezdívka (`Zakaznik.nick`) | **Zůstává** |
| Telefon v rezervaci | **Není samostatné pole** modelu rezervace |
| IP (`ip_adresa`) | **Zůstává** (kód ji nemění) |
| Termín, služby, stav, ID, zaměstnanec | **Zůstávají** |
| `email_hash` | **Zůstává** / doplní se |

Později (~12×30 dní po `konec`, po anonymizaci): soft-delete (`deleted_at`), pak hard-delete včetně NO-show starších než retenční hranice.

#### A3. Odklad kvůli děkovnému e-mailu

Pokud je aktivní post-visit notifikace (`FEATURE_POST_VISIT_EMAIL` + offset &lt; 0) a stav `dokonceno`, anonymizace **čeká na `thank_you_sent_at`**. Do odeslání děkovného mailu (nebo vypnutí podmínky) může plaintext e-mail zůstat **déle než 24 h** od `konec`.

#### A4. Partner **neuloží** zákazníka do Archivníka

- Rezervace žije vlastní retenční dráhou (výše).
- Žádná dlouhodobá karta nevzniká.
- Po anonymizaci Partner v kalendáři typicky vidí jméno/nick + provozní data, ne e-mail.
- Po hard-delete zmizí i anonymizovaný záznam z DB (až na zálohy ~14 dní).

#### A5. Partner **uloží** zákazníka do Archivníka

- Akce „Založit zákazníka“ / ruční create zkopíruje **e-mail + jméno** (z rezervace nebo formuláře); telefon jen pokud ho personál doplní.
- Uloží se do `archivnik.Customer` (a dál objekty, zápisy, assety…).
- **Žádná automatická anonymizace karty po 24 h** — karta je dlouhodobá evidence Partnera, dokud ji Partner (majitel) nesmaže nebo nepožádá o součinnost.
- Vazba rezervace↔karta je **runtime match e-mailu**, ne FK.

#### A6. Poškodí anonymizace rezervace kartu?

**Ne.** `anonymizuj_obsah_rezervace` sahá jen na `Rezervace` / `Zakaznik` (rezervační účet) / `NoShowZaznam` / historii rezervace. `archivnik.Customer` a Bunny assety **nesmaže**.

Poznámka: anonymizace **jedné** rezervace přepíše `Zakaznik.email` u sdíleného rezervačního účtu — to ovlivní ostatní rezervace téhož `Zakaznik`, ale **ne** Archivník kartu (ta má vlastní e-mail).

#### A7. Lze po anonymizaci zpětně spojit rezervaci s kartou?

- Automatický match přes e-mail **padá** (e-mail rezervace už není shodný s kartou).
- FK neexistuje.
- Teoreticky slabá identifikace přes `jmeno_host` / nick (nespolehlivé, není v kódu jako vazba).
- `email_hash` na rezervaci/NO-show **nepropojuje** Archivník (Archivník hash neukládá).

### Schéma (stručně)

```
Online rezervace → plaintext e-mail v Zakaznik/Rezervace
        │
        ├─[Partner NEULOŽÍ kartu]→ jen retenční dráha rezervace
        │         └─(+24h + podmínky) anonymizace e-mailu
        │         └─(~12 měs.) soft/hard delete
        │
        └─[Partner ULOŽÍ kartu]→ archivnik.Customer (vlastní kopie e-mailu/jména…)
                  ├─ karta žije dlouhodobě (bez auto 24h wipe)
                  └─ anonymizace rezervace kartu NEMAŽE; e-mailový match se přeruší
```

### Důkaz

- `backend/rezervace/services/gdpr.py` — `anonymizuj_obsah_rezervace`, `ANONYMIZACE_PO_HODINACH`, `dekujici_notifikace_aktivni`
- `backend/rezervace/services/zivotni_cyklus.py` — `muze_anonymizovat`, soft/hard delete, NO-show úklid
- `backend/rezervace/models.py` — `jmeno_host`, `nick`, `ip_adresa` (telefon u rezervace není)
- `backend/flow/kartoteka_services.py` — `create_customer_from_flow`, `attach_archivnik_customer_links`
- Test: `backend/archivnik/tests_p56a.py` — po smazání karty rezervace/`Zakaznik` zůstávají

### Zjištěný problém

1. **Neaktuální text DPA (F14):** „do 24 h / nelze identifikovat“ — jméno/nick/IP zůstávají; děkovný mail odkládá anonymizaci.  
2. **Technická poznámka:** anonymizace `Zakaznik.email` je per účet, ne per jedna rezervace (vedlejší efekt na sourozence rezervací).  
3. **Žádný problém** v předpokladu, že Archivník karta žije dlouhodobě — systém to tak má.

### Doporučení

- Upravit DPA: rezervace = krátká retenční dráha; Archivník = dlouhodobá kartotéka Správce; anonymizace rezervace kartu nemění.  
- Upřesnit výčet mazaných vs. ponechaných polí a výjimku děkovného mailu.  
- Volitelně (produkt): při anonymizaci mazat i `jmeno_host` / omezit IP — jen pokud to právní chce.

### Velikost případné opravy

| Varianta | Velikost |
|----------|----------|
| Jen text DPA | **S** |
| Doplnit mazání jména/IP v anonymizaci | **S** |
| Oddělit anonymizaci e-mailu per-rezervace vs. sdílený `Zakaznik` | **M** |

---

## B. Výmaz konkrétního zákazníka (F27, F29)

### Současný stav

#### B1–B2. Tlačítko a oprávnění

| Místo | Funkce | Kdo |
|-------|--------|-----|
| **Archivník UI** | „Odstranit zákazníka a jeho data“ + potvrzení přesným `display_name` | Jen **majitel** (`je_spravce` / `ROLE_MAJITEL`); zaměstnanec **403** |
| **FLOW kartotéka** | Delete **není** — jen odkaz „Otevřít kompletní kartu v Archivníku“ | — |
| **Web admin rezervací** | GDPR export / výmaz **rezervačního** `Zakaznik` podle e-mailu | Jen **majitel** (`MajitelPermission`) — **ne** maže Archivník kartu |

#### B3–B4. Co smaže Archivník delete

`smaz_kartoteku_zakaznika`:

1. Smaže Bunny soubory (`storage_key` všech assetů karty) — při chybě Bunny **DB nemění** (retry).
2. V DB smaže: objekty + custom fields, soubory (Asset), zápisy (Entry), připomínky, tagy vazby, Customer.

Ano: objekty, zápisy, poznámky na kartě, fotografie/PDF, připomínky.

#### B5. Historické rezervace a duplicity

- Rezervace a `rezervace.Zakaznik` **zůstávají** (test P56A to dokládá).
- Po anonymizaci rezervace už e-mail nesedí na smazanou kartu.
- Duplicitní karta se stejným e-mailem v salonu nemůže existovat (unique); po smazání lze založit znovu.

#### B6. Co zůstane v jiných modulech po smazání karty

| Modul | Po smazání karty |
|-------|------------------|
| Rezervace / NO-show / e-mail hash | Zůstávají (vlastní lifecycle) |
| Materiálník | Neobsahuje kartu; případné `reservation_ref` zůstává |
| Audit logy | Mohou obsahovat dřívější snapshoty (scrub hesel/tokenů, ne nutně všechno OÚ) |
| Zálohy DB | Až ~14 dní |
| Web Bunny (`webs/salon-…`) | Nedotčeno (veřejná média webu) |

#### B7. Umí Partner kompletní výmaz sám?

**Ne úplně.**

- Kartotéku (Archivník) ano — majitel sám.  
- Rezervační účet + anonymizace rezervací — majitel přes **GDPR výmaz** v adminu rezervací (jiný endpoint, jiný objekt).  
- Komplet „všechny stopy zákazníka ve všech modulech jedním klikem“ **neexistuje**.  
- Ulov centrální admin zásah není pro běžný DSR nutný, pokud majitel použije **obě** funkce a ví o nich.

### Důkaz

- `archivnik/app.js` — UI delete + potvrzení jménem  
- `backend/archivnik/views.py` `CustomerDetailView.delete`  
- `backend/archivnik/kartoteka_delete.py`  
- `flow/customer-card.js` — bez delete  
- `backend/rezervace/views.py` — `AdminGdprExportView` / `AdminGdprVymazView`  
- `backend/rezervace/services/gdpr_admin.py` — `vymaz_zakaznik_na_zadost`  
- `backend/archivnik/tests_p56a.py` — booking zůstává

### Zjištěný problém

- **Neaktuální očekávání / chybějící UX:** DSR „smazat zákazníka“ ≠ jeden kompletní wipe; FLOW nemá delete.  
- **Ne technická chyba** samotného Archivník delete (funguje včetně Bunny).  
- **Chybějící interní postup** pro Partnera: kdy použít Archivník delete vs. GDPR výmaz rezervací.

### Doporučení

- Do DPA/návodu Partnera: dvě cesty (karta vs. rezervace).  
- Volitelně: v FLOW odkaz/tlačítko na Archivník delete pro majitele (ne nový wipe engine).  
- Nedělat plošné mazání rezervací při delete karty (rozbilo by provozní historii).

### Velikost

| Varianta | Velikost |
|----------|----------|
| Dokumentace / DPA text | **XS–S** |
| FLOW odkaz na existující Archivník delete | **XS** |
| Jedno tlačítko „kompletní DSR“ (karta + rezervace) | **M** |

---

## C. Fotografie a dokumenty Bunny / Archivník (F20, F22, F24)

### Současný stav

1. **Přístup UI/API:** Obsah assetu jen přes `/api/archivnik/assets/{uuid}/content/` s `ArchivnikPermission` + filtr `salon`. Cizí tenant → 404 (testováno).  
2. **URL bez přihlášení:** Aplikační content URL **bez tokenu neprojde**. Soubory jsou ale na Bunny Storage pod klíčem `archivnik/{tenant_uuid}/{asset_uuid}.{ext}`. Veřejné webové fotky jdou jinou cestou (`…/salon-{id}/galerie/…`) a vrací se jako **veřejná CDN URL**.  
3. **Oddělení:** Prefix `archivnik/…` vs `…/salon-{id}/…` (web). UI Archivníku **nepoužívá** CDN URL pro soukromé soubory — proxy přes API.  
4. **Při smazání karty:** Bunny delete všech `storage_key` karty, pak DB strom (viz B).  
5. **CDN / EHP:** Storage typicky EU; CDN `*.b-cdn.net` může mít edge mimo EHP (uvedeno v Příloze 3 / PODKLAD).  
6. **Smluvní záruky Bunny:** V repo **není** uložen podepsaný DPA/SCC dokument Bunny; PODKLAD uvádí „SCC/DPF dle Bunny“ jako poznámku. **NELZE OVĚŘIT** z gitu, zda máte aktuální uzavřené podmínky.

### Bezpečnostní riziko (k ověření v Bunny panelu)

Pokud pull zone slouží **celou** storage zónu bez Token Authentication / bez blokace prefixu `archivnik/`, mohl by teoreticky kdokoli s uhádnutým/uniklým `storage_key` stáhnout soubor přímo z CDN **mimo** API. Aplikace klíč do prohlížeče záměrně nedává; riziko = únik klíče + veřejný pull zone.

**Bez schválení nekonfigurovat** — jen ověřit v Bunny: Token Auth / Edge Rule deny `archivnik/*` / oddělená zóna.

### Důkaz

- `backend/archivnik/storage.py` — klíč, `get_bytes`/`put_bytes` s AccessKey  
- `backend/archivnik/views_evidence.py` — `AssetContentView` + `ArchivnikPermission`, `Cache-Control: private`  
- `backend/archivnik/serializers.py` — URL jen API content  
- `backend/salons/bunny.py` — veřejné CDN URL pro web  
- `modernik/subzpracovatele.html`, `dokumenty/PODKLAD_SUBZPRACOVATELE.*`  
- Testy cross-tenant asset content v `backend/archivnik/tests.py`

### Zjištěný problém

- **OK** na aplikační vrstvě (auth proxy).  
- **Bezpečnostní riziko / NELZE OVĚŘIT:** CDN konfigurace pull zone pro prefix `archivnik/`.  
- **Chybějící interní postup:** archivovat Bunny DPA/SCC k Příloze 3.

### Doporučení

1. V Bunny ověřit, že `archivnik/` není veřejně čitelné přes CDN (Token Auth nebo oddělená zóna).  
2. Do interní složky uložit aktuální Bunny DPA/SCC.  
3. DPA text: Partner = správce příloh; Zpracovatel = hosting přes Bunny; soukromé soubory jen oprávněným.

### Velikost

| Varianta | Velikost |
|----------|----------|
| Ověření + případný Edge Rule / Token Auth | **S** |
| Oddělená Bunny zóna pro Archivník | **M** |
| Jen doplnění dokumentace DPA | **XS** |

---

## D. Ukončení spolupráce s Partnerem (F29, F30) — návrh manuálního tlačítka

### Současný stav — co už existuje

| Funkce | Formát | Maže? | Kde |
|--------|--------|-------|-----|
| `export_archivnik_partner` | ZIP (karty + assety) | Ne | management command |
| `export_archivnik_customer` | ZIP jedna karta | Ne | management command |
| `export_zakaznik_data` | JSON | Ne | admin GDPR API |
| `vymaz_zakaznik_na_zadost` | — | Anonymizace rezervačního účtu | admin GDPR API |
| `smaz_kartoteku_zakaznika` | — | Jedna karta + Bunny | Archivník API |
| Deaktivace Materiálníku | — | **Nemaže** data | partner_admin |
| Full `purge_salon` | — | **Neexistuje** | — |

### Kde leží data Partnera (`salon_id` / tenant)

| Úložiště | Obsah |
|----------|--------|
| PostgreSQL (Hetzner) | Salon, rezervace, `Zakaznik`, NO-show, FLOW users, Archivník models, partner_admin (`PlatbaPartnera`, faktury…), audit |
| Redis | Session/cache (krátkodobé) |
| Materiálník SQLite volume `materialnik_data` | Sklad tenant data |
| Bunny | `archivnik/{tenant}/…` + veřejné `…/salon-{id}/…` |
| `www/salonN` / statika | Veřejný web (ne OÚ zákazníků rezervací) |
| Zálohy `./backups/*.gz` | DB (+ config + www) |

### Co smazat při kompletním ukončení (cíl budoucího tlačítka)

1. Export (ZIP Archivník + JSON/CSV provozních dat dle potřeby).  
2. Archivník: všechny karty + Bunny `archivnik/{tenant}/`.  
3. Rezervace / Zakaznik / NO-show / historie / sessions salonu.  
4. FLOW users/sessions, staff dle politiky.  
5. Materiálník tenant data.  
6. Veřejné Bunny média webu (volitelně — spíš brand Partnera).  
7. Statický web — dle obchodního rozhodnutí.  
8. **Nesmazat hned:** `PlatbaPartnera` / účetní doklady Zpracovatele (zákonné uchování).  
9. Zálohy: přirozeně vymizí po `BACKUP_KEEP_DAYS` (default **14**); případný manuální purge konkrétních dumpů = ops.

### Co musí zůstat (orientačně)

- Účetní a daňové záznamy o platbách Partnera Zpracovateli (`PlatbaPartnera`, `ExtraFaktura`, …) — lhůty dle práva (typ. roky, ne dny).  
- Případné bezpečnostní logy po minimální dobu (audit dnes ~12 měs. retenční cron u běžného provozu — při wipe salonu nutno rozhodnout výjimku).  
- Anonymizované agregáty, pokud je právní chce ponechat.

### Retence záloh (ověřeno LIVE read-only)

- `BACKUP_KEEP_DAYS` na LIVE: **nenastaveno → default 14**  
- `backups/` existuje; aktuálně ~9 `.gz`, nejstarší ~7,5 dne, nejnovější ~2 dny (stav k auditu)  
- Po wipe LIVE DB zmizí OÚ ze záloh až doběhem úklidu starších než KEEP_DAYS (ne okamžitě)

### Návrh nejjednoduššího bezpečného řešení (bez implementace)

**Manuální 2-fázové tlačítko v Partner Adminu (jen Ulov admin / superuser):**

1. **Fáze Export** — zavolá existující `export_partner_zip` + volitelný pg dump filtru salonu / JSON rezervací; uloží ZIP mimo produkční volume; vyžaduje potvrzení.  
2. **Fáze Delete** — po zaškrtnutí „export stažen“ a opsání `salon_id`/názvu:  
   - smazat Archivník strom + Bunny prefix `archivnik/{tenant}` (reuse `smaz_kartoteku` ve smyčce / bulk),  
   - smazat/anonymizovat rezervace+NO-show salonu,  
   - wipe Materiálník tenant,  
   - **ponechat** billing tabulky,  
   - zapsat audit „partner_offboard“.  
3. Žádný cron auto-offboard.  
4. Runbook: po Delete počkat ≥ KEEP_DAYS nebo ručně smazat relevantní backup soubory, pokud právní vyžaduje dřívější odstranění z kopií.

### Typ zjištění

- **Neaktuální text DPA Čl. XII** vs. chybějící operationalizace (ne „rozbitá“ funkce).  
- **Chybějící interní postup** + budoucí malý produktový tool.

### Doporučení

Implementovat až po schválení; mezitím DPA formulovat jako součinnost / manuální předání a výmaz.

### Velikost

| Rozsah | Velikost |
|--------|----------|
| Jen runbook + ruční commands | **S** |
| Partner Admin: Export tlačítko (reuse ZIP) | **M** |
| Partner Admin: Export + Delete 2-fázově (vč. Materiálník + Bunny) | **L** |
| + automatický purge záloh / účetní výjimky UI | **XL** |

Předběžný odhad **cílového manuálního tlačítka (export+delete): L**.

---

## E. Provozní nastavení (F17, F22–F24)

### Současný stav

| Kontrola | Výsledek |
|----------|----------|
| **LIVE Sentry** | `SENTRY_DSN` v `.env` **není nastaven**; v kontejneru `api` také **0** → Sentry na LIVE **neaktivní**. (Hodnota DSN se nevypisuje.) |
| **DB zálohy** | Default **14 dní**; LIVE env `BACKUP_KEEP_DAYS` neoverride; adresář `backups/` aktivní |
| **Aplikační logy** | Docker `json-file` driver u `ulov-api-1`; **v repo není** deklarovaná retence `max-size`/`max-file` → faktická retence závisí na hostiteli/Docker default; **NELZE OVĚŘIT** přesný počet dní bez host config |
| **Další aktivní subprocesory OÚ Partnerů mimo Přílohu 3** | Dle kódu + LIVE Sentry off: hlavní zůstávají **Hetzner** + **Bunny** + **SMTP Partnera** (ne subzpracovatel Hakla). GA Measurement ID prázdné. AI/Stripe neaktivní. |

### Důkaz

- LIVE probe (boolean only): `live_env_file_sentry_set 0`, `live_api_container_sentry_set 0`  
- `deploy/backup.sh` — `KEEP_DAYS="${BACKUP_KEEP_DAYS:-14}"`  
- `backend/salon_api/settings.py` — Sentry jen při non-empty DSN  
- `modernik/subzpracovatele.html`  
- Docker inspect log driver `json-file`

### Zjištěný problém

- **OK** vůči tvrzení „Sentry nepoužíváme“ (LIVE).  
- **Chybějící interní postup:** dokumentovat/retencovat Docker logy (riziko PII v exception trace).  
- **Žádná** nová skrytá SaaS pro OÚ zákazníků Partnerů v runtime nenalezena.

### Doporučení

- Držet `SENTRY_DSN` prázdný na LIVE, nebo při zapnutí aktualizovat Přílohu 3 + scrub.  
- Nastavit Docker `log-opts` max-size (ops).  
- Zálohy: 14 dní stačí uvést do DPA u výmazu/záloh.

### Velikost

| Varianta | Velikost |
|----------|----------|
| Log opts + zmínka v DPA o 14denních zálohách | **XS** |
| Zapnutí Sentry „správně“ (Příloha 3 + scrub) | **S** |

---

## Shrnutí pro právní / vedení

| Oblast | Verdikt jednou větou | Primární akce |
|--------|----------------------|---------------|
| **A** | Rezervace se krátkodobě anonymizují; Archivník karta je dlouhodobá a anonymizací rezervace se **nemaže**. | Upravit text DPA (ne plošné mazání karet). |
| **B** | Majitel umí smazat **kartu** v Archivníku (+Bunny); rezervace zůstávají; FLOW delete nemá; GDPR výmaz rezervací je **samostatný**. | Návod Partnera; případně UX odkaz. |
| **C** | API chrání soukromé soubory; CDN konfiguraci Bunny nutno ověřit; DPA/SCC Bunny v repo chybí. | Bunny panel check + založit smlouvy. |
| **D** | Stavební kostky exportu existují; full wipe ne; vhodné manuální 2-fázové tlačítko ~**L**. | Schválit rozsah; mezitím DPA = součinnost. |
| **E** | LIVE Sentry off; zálohy 14 dní; žádný nový skrytý subprocessor OÚ. | Ops log retence; zmínka záloh v DPA. |

**Čeká se na další rozhodnutí vedení — nic se nenasazuje.**
