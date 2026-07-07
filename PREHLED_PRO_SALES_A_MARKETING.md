# ULOV KLIENTY — přehled pro sales a marketing

**Produkt:** Ulov Rezervaci (web + rezervační systém)  
**Značka:** [ULOV KLIENTY](https://www.ulovklienty.cz) · [ULOV SALON](https://www.ulovsalon.cz)  
**Verze dokumentu:** červen 2026  
**Účel:** obchodní a marketingové představení — web salonu na míru, administrace, rezervace, e-maily, recenze, QR platby, NO-show a multi-salon architektura.

---

## Executive summary

**ULOV KLIENTY** dodává salonům krásy a wellness kompletní digitální řešení: **originální web ručně na míru** (ne generická šablona) a pod ním výkonný systém **Ulov Rezervaci** — online rezervace, e-maily, kalendář, QR platby a správa provozu.

Salon získá **web + rezervace + administrace + notifikace v jednom**. Nemusí skládat řešení z pěti různých nástrojů ani platit agenturu za každou drobnou změnu.

**Prezentační web pro zákazníky:** složka `presentace/` — landing s ukázkami, výhodami a formulářem nezávazné poptávky (`POST /api/poptavka/`).

---

## Hlavní výhody projektu

### Pro majitele salonu (obchodní přínos)

| Výhoda | Co to znamená v praxi |
|--------|------------------------|
| **Web, který prodává termíny** | Ne jen fotky — zákazník si rovnou rezervuje. 24/7, i mimo otevírací dobu. |
| **Důvěra a viditelnost** | Bez profesionálního webu může být i špičková služba málo důvěryhodná. Web + rezervace = „tady se můžete spolehnout“. |
| **Méně telefonátů a chaosu** | Kalendář, personál, termíny a notifikace na jednom místě. Majitel má přehled, zaměstnanec vidí jen své. |
| **Více recenzí** | Automatická výzva po návštěvě může **zvýšit získávání hodnocení až o 100 %** — lepší Google, více nových klientů. |
| **Ochrana před NO-show** | Archiv, varování a blokace problematických e-mailů **v rámci salonu** (GDPR, data se mezi salony nesdílí). |
| **QR platby** | Žádost o úhradu e-mailem s QR kódem + QR na displeji kadeřnice (SPAYD, české banky). |
| **Jeden dodavatel** | Web, booking, e-maily, platby, statistiky — bez fragmentace nástrojů. |

### Prodejní diferenciátory (proč my, ne šablona)

| Výhoda | Detail |
|--------|--------|
| **Brand ručně na míru** | Žádné nudné šablony, které sdílí tisíce provozoven. Barvy, typografie, fotky, texty — vše podle domluvy, originálně. |
| **Čtyři ukázkové identity** | Elegance (luxus), Krása (spa), CRAZY (neon), U dvou přátel (kavárna) — stejná platforma, čtyři zcela odlišné světy. |
| **Přátelská administrace** | Salon si sám mění otevírací dobu, ceník, fotky, novinky, dovolené, kolegy — intuitivně, bez programátora. |
| **„Uděláme to za vás“** | Nechce majitel řešit panel sám? Nastavení i úpravy obsahu zvládneme my. |
| **Support 7 dní v týdnu** | Nejsme anonymní SaaS — pomoc s nastavením, školením a provozem každý den. |
| **GDPR připraveno** | Smlouvy DPA, ROPA, audit log, retence, žádný marketing zákazníkům bez souhlasu. |
| **Responzivní na mobilech** | Web i rezervace fungují na telefonu — včetně přihlášení a administrace. |

### Technické výhody (důvěryhodnost u náročnějšího klienta)

- Jeden backend, více salonů — každý izolovaný (`salon_id`), vlastní SMTP, vlastní branding.
- Otevírací doba **automaticky** z rozvrhu aktivního personálu — jeden zdroj pravdy.
- Potvrzení rezervace e-mailem včetně odkazu na potvrzení termínu.
- Cron: připomínky, děkovné e-maily s recenzí, životní cyklus rezervací.
- Bunny.net CDN pro rychlé načítání fotek.

---

## 1. Veřejný web salonu

Každý salon má **vlastní web** napojený na centrální backend. Obsah se načítá z databáze — změna v administraci se hned projeví na webu.

### Sekce webu

| Sekce | Co zákazník vidí |
|-------|------------------|
| **Úvod / O nás** | Název, popis, hero fotka, kontakt, CTA **Rezervovat termín** |
| **Galerie** | Fotogalerie s lightboxem |
| **Personál** | Karty týmu — foto, specializace, popis, týdenní rozvrh |
| **Ceník** | Služby s cenami v Kč (stejné položky jako v rezervacích) |
| **Novinky** | Aktuality s datem a volitelným obrázkem |
| **Kontakt** | Adresa, telefon, e-mail, **otevírací doba** |

### Klíčové vlastnosti webu

- **Responzivní design** — mobil, tablet, desktop (všechny ukázkové salony otestované na mobilech).
- **Ručně navržený vzhled** — ne katalogová šablona; každý salon může mít zcela jinou identitu.
- **Otevírací doba automaticky** ze sjednocení pracovní doby aktivního personálu.
- **Personál na webu = personál v rezervacích** — jeden zdroj pravdy.
- **Rezervační stránka** ve stejném designu jako hlavní web.
- **Prázdné sekce se schovávají** — galerie bez fotek nebo personál bez členů se na veřejném webu nezobrazí.
- **Patička tvůrce** — diskrétní branding ULOV KLIENTY / ULOV SALON (lze stylovat podle salonu).

### Ukázkové salony (demo)

| Salon | Styl | Typ | Port (dev) | Složka |
|-------|------|-----|------------|--------|
| **Salon Elegance** | Tmavý luxus, zlaté akcenty | Kadeřnictví | 5500 | `salon1/` |
| **Studio Krása** | Světlé spa, měkké barvy | Kosmetika | 5501 | `salon2/` |
| **CRAZY** | Neon, hype marketing | Kadeřnictví | 5502 | `salon3/` |
| **U dvou přátel** | Francouzská kavárna, mobilní rám | Barbershop / kavárna | 5503 | `salon4/` |

**Spuštění dema:** doporučeně jeden server z kořene projektu (`python -m http.server 8080`) → `http://localhost:8080/presentace/` a `…/salon1/` atd. Viz `README.md`.

---

## 2. Administrace webu (⚙ panel)

Přístup přes tlačítko **⚙** vpravo dole. **Přátelské rozhraní** — majitel zvládne většinu úprav sám; pokud nechce, uděláme to za něj.

### Co si salon spravuje sám

| Oblast | Možnosti |
|--------|----------|
| **Základní údaje** | Název, popis, adresa, telefon, e-mail |
| **Obrázky** | Hero fotka, galerie (Bunny.net CDN), mazání a výměna |
| **Personál (web)** | Jméno, specializace, popis, foto, rozvrh Po–Ne, zobrazení na webu |
| **Ceník** | Služby a ceny — automaticky služby pro online rezervace |
| **Novinky** | Nadpis, text, volitelný obrázek |
| **E-mail** | SMTP salonu, URL rezervací, test odeslání |
| **Otevírací doba** | Odvozena z personálu; lze ladit přes rozvrhy a absence |

### Role majitele vs. zaměstnanec

- **Majitel (administrátor)** — správa salonu, kalendář, nastavení, personál. **Neprovádí služby** — není v nabídce pro rezervaci, nemá rezervační rozvrh jako kadeřník.
- **Kdo stříhá / provádí služby** — samostatný účet jako **zaměstnanec** s vlastním rozvrhem a kalendářem.
- Oddělené přihlášení personálu — vlastní session, bez „přihlášen bez přihlášení“ chyb.

### Bezpečnost

- Přístup chráněn heslem (nastavitelné v backendu).
- Veřejný web neobsahuje technické návody typu „nahraj v administraci“ — chybové stavy jsou uživatelsky srozumitelné.

---

## 3. Rezervační systém (pro zákazníky)

Stránka **Rezervace** — záložky: **Nová rezervace** · **Moje rezervace** · **Personál** (admin).

### Online rezervace — 4 kroky

1. **Služby** — jedna nebo více najednou, délka, cena, celkový čas.
2. **Termín** — výběr kadeřníka nebo „Je mi to jedno“, volné sloty s ohledem na rozvrh, absence, svátky, blokace, rezervu mezi klienty.
3. **Údaje** — jméno/přezdívka, e-mail, poznámka, GDPR (plnění smlouvy, ne marketingový souhlas).
4. **Potvrzení** — odkaz na storno, soubor **.ics** do kalendáře.

### Zákaznický účet

- Registrace, přihlášení, zapomenuté heslo.
- Přehled budoucích a minulých rezervací, storno jedním klikem.
- Rezervace **bez registrace** u první návštěvy — stačí e-mail.

### Potvrzení e-mailem

- Po vytvoření rezervace zákazník dostane e-mail s odkazem na **potvrzení termínu** (snižuje no-show).
- Storno bez přihlášení přes unikátní odkaz v e-mailu.

---

## 4. Administrace rezervací (Personál)

### Kalendář

- Měsíční pohled, detail dne, timeline rezervací.
- Akce: dokončeno · NO-show · žádost o platbu (QR).

### Personál a provoz

- Zaměstnanci aktivní/neaktivní, rozvrhy, absence (dovolená, nemoc).
- Ruční rezervace (telefon, osobně).
- Číslo účtu pro QR platby u každé kadeřnice.

### Statistiky

- Rezervace, dokončení, storna, NO-show.
- Top služby a nejvytíženější zaměstnanci.

### NO-show archiv

- Pouze v daném salonu, bez sdílení mezi pobočkami.
- 2× NO-show → problematický, 3× → auto-blokace online rezervací.
- Ruční blokace kdykoli.

### Nastavení

- Interval slotů, min./max. předstih, limit storna.
- URL recenze (Google apod.).
- 4 konfigurovatelné e-mailové notifikace s tagy.

---

## 5. E-maily a notifikace

### Okamžité e-maily

| E-mail | Kdy |
|--------|-----|
| Potvrzení rezervace | Po vytvoření |
| Výzva k potvrzení termínu | S odkazem v e-mailu |
| Storno | Zákazník + salon |
| Zapomenuté heslo | Na požádání |
| Test SMTP | Z administrace |

### 4 konfigurovatelné notifikace

| # | Účel | Timing |
|---|------|--------|
| 1 | Připomínka před termínem | cca +24 h předem (cron) |
| 2 | Poděkování + **prosba o recenzi** | cca −2 h po službě (cron) |
| 3 | Upozornění na NO-show | ručně |
| 4 | Žádost o platbu + QR | ručně |

**Recenze:** notifikace č. 2 automaticky vede spokojené zákazníky k hodnocení — bez ručního prosazování u každého klienta. Cíl: **až o 100 % vyšší míra získaných recenzí** oproti bez systému.

### SMTP

- Každý salon vlastní SMTP a odesílatele (e-mail salonu).
- Pro testování lze zkopírovat nastavení referenčního salonu: `python manage.py sync_smtp_salon2`.

---

## 6. QR platby

1. Personál u rezervace → **Požádat o platbu na účet**.
2. Částka, účet (předvyplněno), variabilní symbol.
3. E-mail zákazníkovi s QR + QR na displeji kadeřnice.
4. Zákazník platí přes bankovní aplikaci (SPAYD).

---

## 7. NO-show management

- Data a blokace **pouze v rámci jednoho salonu** (GDPR).
- Modal při NO-show: odeslat upozornění, zablokovat e-mail.
- Archiv s vyhledáváním a zvýrazněním opakovaných případů.

---

## 8. Multi-salon architektura

| Zvlášť pro každý salon | Sdílená infrastruktura |
|------------------------|-------------------------|
| Web, branding, ceník, galerie | Backend, API, CDN |
| Personál, rozvrhy, absence | Referenční státní svátky |
| Zákazníci, rezervace, NO-show | — |
| SMTP, notifikace, parametry rezervací | — |

Nová pobočka = nový frontend + záznam v DB — bez stavby systému od nuly.

---

## 9. GDPR a compliance

- Dokumentace ve složce `dokumenty/` — DPA, přílohy, ROPA (PDF).
- Žádný marketing zákazníkům bez souhlasu; e-mail zákazníka se po službě u salonu skrývá.
- Audit log změn, retence dat, anonymizace.

---

## 10. Technické parametry

| Oblast | Technologie |
|--------|-------------|
| Backend | Django + DRF |
| Frontend | HTML, CSS, vanilla JS |
| API | REST, JSON |
| Obrázky | Bunny.net CDN |
| QR | SPAYD |
| E-maily | SMTP per salon |
| Jazyk | Čeština, Europe/Prague |

---

## 11. Srovnání — bez nás vs. s námi

| Potřeba | Bez ULOV KLIENTY | S ULOV KLIENTY |
|---------|------------------|----------------|
| Web | Šablona jako tisíc jiných / drahá agentura | **Originál na míru** + propojené rezervace |
| Rezervace | Samostatný booking | Integrovaný, napojený na ceník a personál |
| Obsah | Volání programátora | **Přátelská admin** — sám, nebo za vás |
| Recenze | Ruční prosba | Automatická výzva po návštěvě |
| Připomínky | SMS / ručně | Automatické e-maily |
| NO-show | Excel / paměť | Archiv a blokace (GDPR) |
| Platba | Diktování účtu | QR e-mail + displej |
| Podpora | Ticketová fronta | **7 dní v týdnu**, známe váš salon |

---

## 12. Klíčové prodejní argumenty (talking points)

1. **Web, který prodává termíny** — ne jen vizitka na internetu.
2. **Ručně na míru** — žádná šablona, kterou má konkurence ve stejné ulici.
3. **Vše v jednom** — web, rezervace, e-maily, QR, NO-show, statistiky.
4. **Přátelská administrace** — otevírací doba, ceník, fotky, novinky, dovolené, kolegové; nebo **uděláme za vás**.
5. **Více recenzí** — automatická výzva, až **+100 %** získaných hodnocení.
6. **Důvěra** — bez webu zákazník zaváhá, i když jste špička.
7. **Méně administrace** — jeden kalendář, jeden ceník, jeden personál.
8. **GDPR** — připravené smlouvy, žádný marketing, data salonů oddělená.
9. **Support 7 dní** — nejsme anonymní platforma.
10. **Čtyři živá dema** — Elegance, Krása, CRAZY, U dvou přátel — ukažte, ne vykládejte.
11. **Růst** — více kadeřnic, služeb, vlastní doména; systém roste s vámi.
12. **Česko** — SPAYD, svátky, čeština, .ics do kalendáře.

---

## 13. Demo, prezentace a poptávky

### Prezentační web (prodej)

| Položka | URL / cesta |
|---------|-------------|
| Landing | `presentace/index.html` |
| Lokálně (doporučeno) | `http://localhost:8080/presentace/` |
| Jen prezentace | `http://localhost:5510` |
| Formulář poptávky | `POST /api/poptavka/` → e-mail přes SMTP salonu 2 |

### Ukázkové salony

| Salon | Web (dev) | Rezervace |
|-------|-----------|-----------|
| Elegance | `:5500` nebo `/salon1/` | `rezervace.html` |
| Krása | `:5501` nebo `/salon2/` | `rezervace.html` |
| CRAZY | `:5502` nebo `/salon3/` | `rezervace.html` |
| U dvou přátel | `:5503` nebo `/salon4/` | `rezervace.html` |

### Technické (dev)

| Položka | Hodnota |
|---------|---------|
| Backend API | `http://localhost:8000/api` |
| Admin heslo (dev) | `admin123` |
| Cron připomínek | `python manage.py odesli_pripominky` |
| Životní cyklus | `python manage.py rezervace_zivotni_cyklus` |

---

## Kontakt a další kroky

| Kanál | Odkaz |
|-------|-------|
| Web | [www.ulovklienty.cz](https://www.ulovklienty.cz) |
| Salony | [www.ulovsalon.cz](https://www.ulovsalon.cz) |
| Prezentace | `presentace/` — nezávazná poptávka |
| Compliance | `dokumenty/` — smlouvy pro partnery |

**Typický prodejní flow:** prezentace → prohlídka dema (1–4 salony) → konzultace → web na míru → nastavení provozu (sami nebo za klienta) → spuštění → support.

---

*Dokument pro interní potřeby sales a marketingu ULOV KLIENTY. Aktualizováno červen 2026.*

**PDF verze:** spusťte `python dokumenty/generate_sales_pdf.py` → soubor `dokumenty/pdf/PREHLED-pro-sales-a-marketing.pdf`
