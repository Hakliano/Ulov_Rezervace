# ULOV KLIENTY — přehled funkcí a painů (sales & marketing)

**Rodina produktů:** Moderník · FLOW · Materiálník  
**Mateřská značka:** [ULOV KLIENTY](https://www.ulovklienty.cz)  
**Verze dokumentu:** srpen 2026  
**Účel:** interně pro obchod a marketing — co dnes opravdu umíme, jaké bolesti provozovny řešíme, co ukázat na demu. Není to smlouva (smlouvy → `PODKLAD_PRO_PARTNERY.md` + `dokumenty/`).

---

## Executive summary

**Jedna věta:** Provozovna dostane web, který prodává termíny, denní provoz v jedné aplikaci FLOW a volitelně sklad Materiálník — jeden login, méně telefonů, méně chaosu u kasy i ve skladu.

ULOV KLIENTY není jeden „booking plugin“. Je to sada produktů kolem jedné platformy:

| Produkt | Co to je | Pro koho |
|---------|----------|----------|
| **Moderník** | Digitální provozovna: web na míru + online rezervace + FLOW + podpora. Hlavní obchodní nabídka. | Salon, ordinace, řemeslo, autoservis, studio… |
| **FLOW** | Každodenní pracovní prostředí týmu (kalendář, karty, mail, platby, dovolené). Součást Partnerství Moderník. | Majitel + personál |
| **Materiálník** | Sklad, receptury, nákup, odečet spotřeby. Samostatně, nebo levněji s Moderníkem. | Provozovny, které spotřebovávají materiál |
| **Custom Digital Services** | Individuální vývoj (chatbot / digitální recepční, speciální weby). Není součástí měsíčního Partnerství. | Na poptávku |

Zákazník provozovny vidí **veřejný web a rezervace**. Tým vidí **FLOW** (a volitelně **Materiálník**). Majitel spravuje obsah webu v **⚙** na webu provozovny.

---

## Co provozovně ulehčujeme (pain → řešení)

Tohle je jádro marketingu. Ne „máme CRM“, ale **co jim odpadá**.

| Pain v provozu | Co se děje bez nás | Co děláme my |
|----------------|--------------------|--------------|
| Telefony během služby | Zákazník volá, než dojde na řadu. Personál skáče od zákazníka k telefonu. | Online rezervace 24/7. Zákazník se objedná sám, i když je zavřeno. |
| Papír / Excel / WhatsApp kalendář | Dvojité termíny, zapomenuté rezervace, nikdo neví, kdo má volno. | Jeden kalendář ve FLOW. Rozvrh, dovolené, rezervace na jednom místě. |
| Web, který nic neprodá | Šablona jako soused, nebo drahá agentura za každou změnu textu. | Originální web na míru. Změna ceníku / fotky / novinky v ⚙ bez programátora. |
| „Kdo k nám vlastně chodí?“ | Jméno v diáři, nic víc. Další kadeřnice neví, co zákazník chtěl minule. | Karta zákazníka: kontakt, poznámky, historie, nová rezervace z karty. |
| Zapomenuté termíny / no-show | Prázdné křeslo, ztracený čas. | Připomínka e-mailem, výzva k potvrzení termínu, archiv NO-show, blokace opakovaných hříšníků **jen v dané provozovně**. |
| Recenze se nežádají | U kasy je trapné prosit. Google stojí. | Automatický děkovný e-mail s odkazem na recenzi po službě. |
| Platba „nadiktujte si účet“ | Zákazník odchází, převod se odkládá. | QR (SPAYD) e-mailem i na displeji. Záloha předem. |
| Dovolená = chaos | Kdo přebírá klienty? Kdo schválil volno? | Žádost → schválení majitelem → převod rezervace nebo storno s omluvou. |
| Došla barva / materiál v půlce dne | Nákup od oka, večerní dohadování „co chybí“. | Materiálník: minimum, kritický stav, nákupní seznam, receptura ke službě. Po „Proběhla“ ve FLOW nabídne odečet. |
| Pět nástrojů, pět hesel | Web u agentury, booking jinde, sklad v Excelu, mail v telefonu. | Web + rezervace + FLOW + (volitelně) sklad. Stejné přihlášení FLOW i Materiálník. |
| Sklad nesmí shodit provoz | Když „systém skladu“ spadne, nejde kasa. | Rezervace se **nikdy** neblokuje, když Materiálník zrovna neodpoví. Odečet lze dodělat později. |
| Majitel vs. personál | Všichni vidí všechno, nebo nikdo nic. | Majitel vidí provozovnu. Personál svoje (případně přehled bez tlačítek). Správa jen majitel. |
| GDPR strach | Sdílené Excel tabulky, recenze z osobního mailu. | Data salonů oddělená. DPA, retence, audit. Žádné marketingové newslettery zákazníkům. |

**Pro majitele věta:** Méně telefonů, méně večerní administrativy, kalendář plný bez dohánění, recenze bez žebrání u kasy, materiál bez pátečního překvapení.

**Pro personál věta:** Můj den, moje rezervace, karta zákazníka, QR na platbu — v telefonu v prohlížeči, bez instalace.

---

## Mapa produktů (co k čemu patří)

```
ZÁKAZNÍK provozovny          TÝM provozovny              MAJITEL
─────────────────            ──────────────              ───────
Veřejný web                  FLOW                        Web ⚙ (obsah, SMTP, IMAP)
Rezervace (4 kroky)          Materiálník (volitelně)     FLOW Správa
Moje rezervace / účet        Stejný login                Platby partnera (ULOV)
E-maily (potvrzení, …)       Interní banner
```

| Potřeba | Produkt | Balíček |
|---------|---------|---------|
| Web, který vypadá jako oni | Moderník | Partnerství / partnerský web / jednorázový web |
| Objednávky 24/7 | Online rezervace | Partnerství |
| Denní provoz týmu | FLOW | Partnerství |
| Sklad a spotřeba | Materiálník | Samostatně, nebo +99 Kč k Moderníku |
| Růst (QR recenze, vizitky, cesta, video…) | Program růstu | Vstupní nastavení / příplatek |
| Chatbot / speciální vývoj | CDS | Individuálně — **není** v měsíční ceně Moderníku |

---

## 1. Moderník — digitální provozovna

**Web:** [www.modernik.cz](https://www.modernik.cz)  
**Co prodáváme:** „Vy se věnujte zákazníkům — o digitální chod se postaráme.“

Moderník = **web na míru + rezervace + FLOW + osobní podpora**. Materiálník je volitelný doplněk. Program růstu je volitelná roční péče.

### 1.1 Veřejný web provozovny

Každá provozovna má **vlastní web** (ne katalogovou šablonu). Obsah se bere z databáze — změna v ⚙ se hned projeví.

| Sekce | Co zákazník vidí |
|-------|------------------|
| Úvod / O nás | Název, popis, hero, kontakt, CTA Rezervovat |
| Galerie | Fotogalerie s lightboxem |
| Personál | Karty týmu — foto, specializace, popis, týdenní rozvrh |
| Ceník | Služby a ceny (stejné položky jako v rezervacích) |
| Novinky | Aktuality s datem a volitelným obrázkem |
| Kontakt | Adresa, telefon, e-mail, **otevírací doba** |

**Vlastnosti webu**

- Responzivní (mobil, tablet, desktop).
- Ručně navržený vzhled — barvy, typografie, fotky, texty podle provozovny.
- Otevírací doba se skládá z pracovní doby aktivního personálu (jeden zdroj pravdy).
- Personál na webu = personál v rezervacích.
- Rezervační stránka ve stejném designu.
- Prázdné sekce se schovají (galerie bez fotek, tým bez členů).
- Logo, favicon, banner pro tým.
- Diskrétní patička tvůrce (ULOV / Moderník).
- Vlastní doména po dohodě; jinak adresa v rámci spolupráce.

### 1.2 Administrace webu (⚙)

Tlačítko **⚙** na webu provozovny. Přátelské — majitel zvládne většinu sám; pokud nechce, uděláme to za něj.

| Oblast | Co se spravuje |
|--------|----------------|
| Základ | Název, popis, adresa, telefon, e-mail |
| Obrázky | Hero, galerie (Bunny.net CDN), mazání a výměna |
| Personál (web) | Jméno, specializace, popis, foto, rozvrh Po–Ne, zobrazení na webu |
| Ceník | Služby, ceny, délky — automaticky do rezervací |
| Novinky | Nadpis, text, volitelný obrázek |
| E-mail | SMTP provozovny, URL rezervací, IMAP (FLOW Mail), test odeslání |
| Banner FLOW | Interní oznámení týmu („Dnes nejde voda“) |
| Heslo majitele | Změna hesla (ve FLOW se heslo majitele nemění) |
| Vstup do FLOW | Tlačítko Přejít do FLOW |

**Role**

- **Majitel** — správa webu a FLOW. Na webu se jako „kdo stříhá“ nenabízí, pokud není evidovaný jako zaměstnanec se službami.
- **Zaměstnanec** — vlastní FLOW účet, vlastní rozvrh a kalendář.
- Zákazník provozovny **nemá** ⚙ ani FLOW.

### 1.3 Online rezervace (pro zákazníky)

Stránka Rezervace: **Nová rezervace** · **Moje rezervace**.

**Čtyři kroky**

1. **Služby** — jedna nebo více, délka, cena, celkový čas.
2. **Termín** — konkrétní člověk, nebo „Je mi to jedno“. Volné sloty berou v úvahu rozvrh, absence, svátky, blokace, rezervu mezi klienty.
3. **Údaje** — jméno/přezdívka, e-mail, poznámka, seznámení se zásadami (plnění smlouvy, **ne** marketingový souhlas).
4. **Potvrzení** — odkaz na storno, soubor **.ics** do kalendáře.

**Zákaznický účet**

- Registrace, přihlášení, zapomenuté heslo.
- Přehled budoucích a minulých rezervací, storno jedním klikem.
- První návštěva **bez registrace** — stačí e-mail.

**Potvrzení a storno**

- E-mail s odkazem na **potvrzení termínu** (snižuje no-show).
- Storno bez přihlášení přes unikátní odkaz v e-mailu.
- Pravidla storna (kolik hodin předem) nastaví majitel.

### 1.4 Program růstu (volitelně)

Není v každé měsíční platbě. Na webu Moderníku jako roční péče / vstupní varianta Partnerství.

| Fáze | Co partner dostane |
|------|--------------------|
| Start | Meeting, fotky, otevírací doby, sítě s odkazovostí, pomoc s e-mailovými texty |
| ~3 měsíce | QR stojánky / QR·NFC kartičky na Google recenze |
| ~6 měsíců | Vizitky, grafika, bannery, e-poukazy |
| ~9 měsíců | Cesta k provozovně (grafika / video) — nasazení na web |
| ~12 měsíců | Výroční servis webu, doporučení, možnost rebrandu, sleva na nové služby |

Doplňky (vizitky, QR, e-poukazy, bannery, video) lze objednat i mimo program.

### 1.5 Osobní podpora

Ne anonymní SaaS. WhatsApp, e-mail, podle potřeby telefon. Zakladatel zná provozovnu. Úpravy webu v Partnerství **v ceně** (na rozdíl od jednorázového webu 300 Kč/h).

---

## 2. FLOW — denní provoz týmu

**LIVE:** [www.ulovklienty.cz/flow/](https://www.ulovklienty.cz/flow/)  
**Co to je:** Pracovní den majitele a personálu. Veřejný web a formulář rezervací zůstávají na webu provozovny.

FLOW už běží v **mobilním prohlížeči** (responzivní web). Nativní aplikace v Google Play / App Store **zatím není** — viz kap. 12.

### 2.1 Přístup

| Téma | Jak to funguje |
|------|----------------|
| Přihlášení | E-mail + heslo (e-mail globálně unikátní) |
| Session | Token, řádově desítky dní |
| Majitel | Stejné heslo jako web ⚙; ve FLOW se nemění |
| Pracovník | Vlastní účet; heslo v záložce Účet (min. 8 znaků, písmeno + číslo) |
| Aktivace pracovníka | Majitel ve FLOW: vytvořit přístup, dočasné heslo, e-mail |
| Blokace vstupu | Majitel může zakázat FLOW (zaměstnanec na webu zůstává) |
| Overview | Vybraný pracovník vidí přehled všech rezervací **bez** provozních tlačítek |
| Stejný login | Materiálník (když je zapnutý) — stejný účet, žádné druhé heslo |

**Alerty majitele:** platba ULOV po splatnosti, žádosti o volno, rizikové rezervace, nepřečtené maily. Interní banner z webu ⚙.

### 2.2 Záložky — co kdo vidí

| Záložka | Majitel | Personál |
|---------|---------|----------|
| **Přehled (Overview)** | Týden, KPI, top služby, personál, dnes, stav skladu (když je Materiálník) | Jen s `visible_overview`, bez akcí |
| **Můj den** | Rezervace / absence, akce | Vlastní rezervace, akce jen na svých |
| **Kalendář** | Měsíc + den, zadání rezervace | Vlastní rozvrh, zadání na sebe |
| **Zákazníci** | Karty, historie, nová rezervace z karty | Stejně v rozsahu provozovny |
| **Mail** | Sdílená schránka (když IMAP v ⚙) | Stejná schránka |
| **Hříšníci** | NO-show archiv, blokace e-mailů | Ne |
| **Staff / Manager obsluhuje** | Personál, kdo co dělá | Ne |
| **Pracovní doba** | Správa přes personál | Jen náhled |
| **Dovolená** | Vlastní volno + správa žádostí | Žádost o volno |
| **Platby** | Splatnosti ULOV, QR, PDF faktury (čtení) | Ne |
| **Pravidla / Šablony / Audit** | Rezervační pravidla, e-maily, historie | Ne |
| **Správa** | 9 oblastí (níže) | Ne (403) |
| **Účet** | Info (heslo na webu) | Změna vlastního hesla |
| **Sklad — Materiálník** | Odkaz, když je modul aktivní | Stejně |

### 2.3 Správa (jen majitel)

| Oblast | Co dělá |
|--------|---------|
| Rezervační pravidla | Interval slotů, min. předstih, max. dopředu, storno (h), platnost odkazu potvrzení, auto-potvrzení rezervací personálu, URL recenzí |
| E-mailové šablony | Předmět, tělo, timing, zapnutí — transakční maily zákazníkům |
| Personál a přístupy | Přidat pracovníka, e-mail, účet pro QR, rozvrh Po–Ne, FLOW přístup, overview, blokace, reset hesla |
| Přiřazení služeb | Kdo poskytuje které položky ceníku |
| Žádosti o volno | Zapsat absenci, schválit / zamítnout, po schválení převést rezervaci nebo stornovat s omluvou |
| Platby partnera | Stav, částky, QR, historie, stažení PDF faktury ULOV |
| NO-show / hříšníci | Archiv, hledání, blokace / odblokování e-mailu pro **online** rezervace |
| Audit log | Historie změn v provozovně |
| Statistiky | Rezervace, dokončení, storna, NO-show, top služby a personál |

### 2.4 Akce u rezervace

| Akce | Význam |
|------|--------|
| **Proběhla** | Dokončení. Když je Materiálník, nabídne se odečet spotřeby (lze přeskočit). |
| **NO-show** | Nedorazil + volitelný e-mail |
| **Platba QR** | E-mail zákazníkovi s QR (SPAYD) + QR na displeji |
| **Požádat o zálohu** | QR záloha předem |
| **Záloha OK** | Potvrzení, že záloha přišla |
| **Storno** | Ze strany provozovny + e-mail (řešení zálohy, pokud byla) |
| **Převod** | Na jiného pracovníka (typicky při dovolené) |
| **Zadat rezervaci** | Telefon / osobně: služby, termín, jméno, e-mail nebo „nemá e-mail“, poznámky |

Ruční rezervace i online rezervace končí ve stejném kalendáři.

### 2.5 Kartotéka (záložka Zákazníci)

Nasazeno na LIVE.

- Návrh karty (jméno, e-mail, telefon, popis).
- Žádost o potvrzení e-mailem → zákazník potvrdí odkazem → karta **aktivní**.
- Historie návštěv na kartě.
- Interní poznámky pro tým.
- **Nová rezervace z aktivní karty** — předvyplní jméno a e-mail.
- Z rezervace odkaz „Otevřít kartu“, pokud e-mail sedí na aktivní kartu.
- Unique e-mail v rámci provozovny. Data se mezi provozovnami nesdílí.
- GDPR: evidence je funkce partnera (správce), ne marketingová databáze ULOV.

### 2.6 FLOW Mail

- Zapnutí IMAP/SMTP: **web ⚙**, ne ve FLOW.
- Ve FLOW: příchozí (čte schránku on-demand, celý inbox se neukládá do naší DB), odeslané, nový mail, odpověď, náhled před odesláním.
- Účel: firemní komunikace v provozním prostředí, ne soukromý Gmail personálu.

### 2.7 Co ve FLOW není (a má to tak zůstat)

| Oblast | Kde to je |
|--------|-----------|
| Texty a fotky webu, ceník, novinky | Web ⚙ |
| SMTP / IMAP credentials | Web ⚙ |
| Heslo majitele | Web ⚙ |
| Veřejný formulář rezervace | `rezervace.html` na webu |
| Potvrzení plateb partnera ULOV | Partner-admin (my) |
| Sklad (materiály, inventura) | Materiálník — FLOW jen nabízí odečet a odkaz |

---

## 3. Materiálník — sklad a spotřeba

**Web produktu:** [www.materialnik.cz](https://www.materialnik.cz)  
**Aplikace LIVE:** [www.ulovklienty.cz/sklad/](https://www.ulovklienty.cz/sklad/)  
**Slogan:** Má přehled o tom, co spotřebujete.

Funguje **sám** (bez webu a rezervací), nebo **společně s Moderníkem**. Když je napojený na FLOW: stejné přihlášení, po „Proběhla“ návrh spotřeby, ve FLOW Přehledu widget skladu.

**Železné pravidlo produktu:** kalendář a rezervace se kvůli skladu **nezastaví**. Když Materiálník neodpoví, rezervace platí, odečet se dodělá později.

### 3.1 Co aplikace umí

| Oblast | Funkce |
|--------|--------|
| **Přehled** | Hodnota zásob (podle nákupních cen), počet pod minimem, kriticky nízké, otevřené nákupy |
| **Materiály** | Název, kategorie, jednotka, minimum, kritický stav, dodavatel, nákupní cena |
| **Materiály ke službě (receptury)** | Předpis spotřeby ke službě z ceníku. Personál může množství na místě upravit. Prázdné pole = neodečítá se. |
| **Pohyby / historie** | Stav se počítá z pohybů, ne z „tipu na papíře“ |
| **Inventura** | Zápis skutečného stavu |
| **Nákupní seznam** | Položka pod minimem se objeví sama |
| **Upozornění** | Dochází / kriticky málo |
| **Odečet spotřeby** | Ručně v Materiálníku, nebo nabídka z FLOW po dokončení služby |
| **Dodavatelé, kategorie, jednotky** | Číselníky |
| **SSO** | Stejný účet jako FLOW (když je tenant napojený) |

### 3.2 Propojení s FLOW

1. Modul zapne provozovatel platformy (partner-admin / `zapni_materialnik`).
2. Ve FLOW se objeví tlačítko **Sklad — Materiálník**.
3. Po **Proběhla** modal: obvyklé množství z receptury, personál vyplní jen to, co vzal.
4. Na Přehledu majitele: položky pod minimem / kritické.
5. Outbox: když sklad zrovna nejde, událost se dohraje — rezervace už je uložená.

### 3.3 Ceny (veřejný web, akce do 31. 12. 2026)

| Varianta | Akce | Potom / běžně |
|----------|------|----------------|
| Samostatně | **299 Kč / měsíc** | 499 Kč / měsíc |
| Společně s Moderníkem | **+99 Kč / měsíc** | stejný příplatek v nabídce |

---

## 4. E-maily a notifikace (transakční, ne marketing)

Žádné newslettery zákazníkům provozovny. Každá provozovna má **vlastní SMTP** (mail odchází jako salon, ne jako „noreply ULOV“).

### Okamžité

| E-mail | Kdy |
|--------|-----|
| Potvrzení rezervace | Po vytvoření |
| Výzva k potvrzení termínu | Odkaz v e-mailu |
| Storno | Zákazník + provozovna |
| Zapomenuté heslo | Na požádání |
| Žádost o potvrzení karty zákazníka | Z FLOW |
| Test SMTP | Z ⚙ |

### Nastavitelné notifikace (cron)

| Účel | Typicky |
|------|---------|
| Připomínka před termínem | ~24 h předem |
| Poděkování + **prosba o recenzi** | po službě |
| Upozornění na NO-show | ručně z FLOW |
| Žádost o platbu / zálohu + QR | ručně z FLOW |

**Recenze:** po návštěvě odkaz na Google (URL nastaví majitel). Cíl pro copy: až **+100 %** získaných hodnocení oproti ručnímu prosazování u kasy — používejte jako cíl, ne jako garantovanou statistiku každé provozovny.

---

## 5. QR platby a zálohy

České banky, formát **SPAYD**.

1. U rezervace → požádat o platbu nebo zálohu.
2. Částka, účet (předvyplněno z pracovníka / živnosti), VS.
3. E-mail zákazníkovi s QR + stejné QR na displeji u kasy.
4. **Záloha OK** když peníze dorazí.
5. Při stornu systém pomáhá s komunikací o vrácení / přesunu zálohy.

Není to platební brána (GoPay apod.) — je to **rychlý převod z bankovní aplikace**. To je záměr: nízké tření, žádný PSP poplatek v produktu.

---

## 6. NO-show

- Evidence **jen v rámci jedné provozovny** (GDPR — nesdílí se mezi salony).
- Modal: odeslat upozornění, zablokovat e-mail pro **online** rezervace.
- Archiv s vyhledáváním, zvýraznění opakování.
- Typicky: 2× → problematický, 3× → auto-blokace online (ruční blokace kdykoli).
- Osobní / telefonickou rezervaci může personál pořád zadat ručně.

---

## 7. Multi-provozovna a vertikály

Jeden backend, data izolovaná (`salon_id` / tenant). Každá provozovna: vlastní web, ceník, personál, zákazníci, SMTP, NO-show, karty, volitelně vlastní tenant Materiálníku.

Stejná platforma, jiný brand:

| Vertikála | Příklady dem |
|-----------|----------------|
| **Salony / krása** | Kudrlinka, Elegance, Krása, CRAZY, U dvou přátel, Wellness Gold, Klid, Silver, RELAX |
| **Provozovny** | Fraňek Autoservis, MotorBay, Ateliér 42, RentGo |
| **Řemesla** | VodaPro, VOLT, Ateliér Domov |
| **Ordinace / zdraví** | Bělice, Movium, PawCare |

Nová pobočka = nový frontend + záznam v DB, ne stavba systému od nuly.

---

## 8. GDPR a compliance (obchodní argument, ne právní text)

- DPA, přílohy, ROPA — složka `dokumenty/` (HTML + PDF).
- Právní mapování funkcí: `For Compliance v1.md`.
- Žádný marketing zákazníkům provozovny z naší strany.
- E-mail zákazníka se po službě u personálu skrývá (provozní pravidlo).
- Audit log, retence, anonymizace životního cyklu rezervace (`ZIVOTNI_CYKLUS_REZERVACE.md`).
- Karty zákazníků: samostatná evidence partnera, potvrzení zákazníkem.

---

## 9. Obchodní nabídka (orientačně, stav srpen 2026)

Definitivní čísla do smluv = `PODKLAD_PRO_PARTNERY.md` a VOP. Níže to, co je na webech.

| Nabídka | Cena (akce do 31. 12. 2026) | Běžně | Web | Rezervace | FLOW | Materiálník |
|---------|-----------------------------|-------|-----|-----------|------|-------------|
| Web jednorázově | 4 000 Kč jednorázově | — | ano | ne | ne | ne |
| Partnerský web | **199 Kč / měs.** | 299 Kč | ano | ne | ne | ne |
| **Partnerství Moderník** | **499 Kč / měs.** | 799 Kč | ano | ano | ano | +99 Kč |
| Materiálník samostatně | **299 Kč / měs.** | 499 Kč | — | — | — | ano |
| Program růstu | vstupní varianta / roční péče | viz web | — | — | — | — |

Vstupní nastavení Partnerství (smlouvy): **2 999 Kč** bez Programu růstu, **3 999 Kč** včetně. Úpravy webu v Partnerství v ceně; u jednorázového webu 300 Kč/h.

---

## 10. Srovnání — bez nás vs. s námi

| Potřeba | Bez nás | S námi |
|---------|---------|--------|
| Web | Šablona / drahá agentura | Originál na míru + rezervace ve stejném designu |
| Termíny | Telefon, papír, cizí booking | Integrované, ceník + personál + rozvrh |
| Obsah webu | Volání grafika | ⚙ sám, nebo uděláme za vás |
| Pracovní den | Excel, WhatsApp, paměť | FLOW — můj den, kalendář, karty, mail |
| Recenze | Ruční prosba | Automatická výzva po návštěvě |
| NO-show | „Už k nám nesmí“ z hlavy | Archiv + blokace (GDPR, jen tato provozovna) |
| Platba | Diktování účtu | QR e-mail + displej, záloha |
| Sklad | Od oka, dojde v pátek | Receptura + minimum + nákupní seznam |
| 5 nástrojů | 5 faktur, 5 hesel | Jeden dodavatel, jeden login na provoz |
| Podpora | Ticket #45821 | Člověk, který systém staví |

---

## 11. Talking points (12 vět do pitchu)

1. **Web, který prodává termíny** — ne vizitka na internetu.
2. **Ručně na míru** — ne šablona, kterou má konkurence ve stejné ulici.
3. **FLOW je pracovní den** — kalendář, karty, mail, platby, tým. Ne další „admin panel“.
4. **Materiálník hlídá spotřebu** — receptura ke službě, nákup podle stavu, ne podle dojmu.
5. **Sklad neshodí kasa** — rezervace platí, i když odečet počká.
6. **Jeden login** — FLOW i Materiálník, majitel i personál s různými právy.
7. **Méně telefonů** — zákazník se objedná v noci, vy pracujete ve dne.
8. **Více recenzí** — děkovný e-mail, ne trapas u kasy.
9. **QR a zálohy** — české banky, bez platební brány.
10. **GDPR v pořádku** — oddělená data, smlouvy, žádný náš newsletter na jejich klienty.
11. **Stejný motor, jiný svět** — salon, zubař, instalatér, autoservis. Ukažte demo, nestrachujte se z „jen krása“.
12. **Člověk, ne chatbot** — podpora zakladatele. *(Digitální recepční je samostatná CDS služba na poptávku, ne součást měsíčního Partnerství.)*

---

## 12. Co dnes **nemáme** (ať marketing neslibuje)

Buďte v copy přesní. Tohle není v produktu:

| Téma | Stav |
|------|------|
| Nativní app FLOW v Google Play / App Store | Není. Funguje v mobilním prohlížeči. Obal (Capacitor) je reálná cesta 6–12 týdnů, ne přepis. |
| Marketingové kampaně / newslettery zákazníkům | Záměrně ne. Transakční e-maily ano. |
| Platební brána (karta online) | Ne. QR převod SPAYD. |
| Sdílení „hříšníků“ mezi provozovnami | Ne — GDPR. |
| Chatbot / digitální recepční v Partnerství | Ne automaticky. CDS na poptávku. |
| Materiálník u každého partnera | Modul se **zapíná**. Bez zapnutí ve FLOW není. |
| Program růstu v každé měsíční platbě | Jen zvolená vstupní / roční varianta. |

---

## 13. Live dema a URL (ukázat, ne vykládat)

### Produkty

| Co | URL |
|----|-----|
| Hub ULOV | https://www.ulovklienty.cz/ |
| Moderník | https://www.modernik.cz/ |
| Materiálník (landing) | https://www.materialnik.cz/ |
| FLOW | https://www.ulovklienty.cz/flow/ |
| Materiálník (aplikace) | https://www.ulovklienty.cz/sklad/ |

### Salony (krása)

| Demo | Web |
|------|-----|
| **Kudrlinka** (FLOW + Materiálník) | https://www.ulovklienty.cz/salon19/ |
| Salon Elegance | https://demo1.ulovklienty.cz/ |
| Studio Krása | https://demo2.ulovklienty.cz/ |
| CRAZY | https://demo3.ulovklienty.cz/ |
| U dvou přátel | https://demo4.ulovklienty.cz/ |
| Wellness Gold | https://demo5.ulovklienty.cz/ |
| Salon Klid | https://demo6.ulovklienty.cz/ |
| Silver kosmetika | https://demo7.ulovklienty.cz/ |
| RELAX | https://demo8.ulovklienty.cz/ |

Kudrlinka a Studio Krása mají na LIVE zapnutý Materiálník (stejný login jako FLOW). Testovací účty: `deploy/TESTOVACI_PRISTUPY.md` — **neposílejte hesla do veřejného marketingu**.

### Další vertikály

| Demo | URL |
|------|-----|
| Fraňek Autoservis | https://franek-autoservis.cloud/ |
| MotorBay | https://www.ulovklienty.cz/provoz-autoservis/ |
| Ateliér 42 | https://www.ulovklienty.cz/provoz-studio/ |
| RentGo | https://www.ulovklienty.cz/provoz-pujcovna/ |
| VodaPro | https://www.ulovklienty.cz/remesla-instalater/ |
| VOLT | https://www.ulovklienty.cz/remesla-elektrikar/ |
| Ateliér Domov | https://www.ulovklienty.cz/remesla-rekonstrukce/ |
| Bělice | https://www.ulovklienty.cz/zdravi-dental/ |
| Movium | https://www.ulovklienty.cz/zdravi-fyzio/ |
| PawCare | https://www.ulovklienty.cz/zdravi-veterina/ |

**Prodejní flow:** hub / Moderník → 2–3 dema (různé vertikály) → FLOW (Kudrlinka) → Materiálník (stejný login) → poptávka `POST /api/poptavka/`.

---

## 14. Technika jednou větou (pro náročného klienta)

Django + REST, PostgreSQL, Docker na Hetzneru, HTTPS, Bunny CDN, SMTP per provozovna, QR SPAYD, Čeština / Europe/Prague. Staging a LIVE oddělené. Multi-tenant: data se nemíchají. Materiálník je **samostatná aplikace** (vlastní DB), napojená přes rozhraní — proto sklad nesmí shodit rezervace.

---

## Kontakt a související dokumenty

| Kanál / dokument | Kde |
|------------------|-----|
| Hub | https://www.ulovklienty.cz |
| Moderník | https://www.modernik.cz |
| Materiálník | https://www.materialnik.cz |
| Ceník a FLOW do smluv | `PODKLAD_PRO_PARTNERY.md` |
| GDPR / právní mapování | `For Compliance v1.md`, `dokumenty/` |
| VOP | `presentace/vop.html` |
| Testovací loginy (interně) | `deploy/TESTOVACI_PRISTUPY.md` |

---

## Historie tohoto dokumentu

| Datum | Změna |
|-------|--------|
| červen 2026 | První sales verze — web + rezervace, 4 dema, bez FLOW jako produktu |
| **srpen 2026** | Celá rodina: Moderník, FLOW (včetně karet, mailu, záloh, overview), Materiálník a napojení, vertikály, Kudrlinka, pain mapa, co neslibovat |

*Interní podklad sales a marketingu ULOV KLIENTY. Ceny a právní text vždy ověřit vůči webu a `PODKLAD_PRO_PARTNERY.md`.*

**PDF:** z kořene projektu  
`python dokumenty/generate_sales_pdf.py`  
→ `dokumenty/pdf/PREHLED-pro-sales-a-marketing.pdf`  
→ HTML náhled `dokumenty/prehled-pro-sales-a-marketing.html`
