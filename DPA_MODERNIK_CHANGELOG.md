# Changelog — DPA MODERNÍK (návrh ke schválení)

| Položka | Hodnota |
|--------|---------|
| Soubor | `modernik/dpa.html` |
| Stav | **finální znění — ke schválení před LIVE** (staging) |
| Datum dokumentu | říjen 2026 |
| Účinnost | Až po schválení vedením a výslovném nasazení na LIVE — **ne zpětně** |
| Podklady | `DPA_MODERNIK_TECHNICKY_AUDIT.md`, `DPA_MODERNIK_DOPLNUJICI_ANALYZA.md` |
| Produktový kód | **Beze změny** |
| LIVE | **Beze změny** |

---

## Změny podle článků

### Meta / lead / Čl. XIII

| | |
|--|--|
| **Původní význam** | Datum „září 2026“, stav „platné znění“ bez označení návrhu. |
| **Nový význam** | Datum říjen 2026, stav „návrh ke schválení“; účinnost až schválením/zpřístupněním; Čl. XIII/7 chrání existující vztahy do schválení. |
| **Zjištění** | F34 |

### Článek I

| | |
|--|--|
| **Původní význam** | Předmět: rezervace, FLOW, Materiálník. |
| **Nový význam** | Explicitně doplněn **Archivník** (evidence klientů / kartotéka). |
| **Zjištění** | F20, F21 |

### Článek II

| | |
|--|--|
| **Původní význam** | Rezervace „nejsou pro marketing“; evidence jen pod FLOW; bez Archivníku a příloh. |
| **Nový význam** | Rezervace: provozní kontakty + zákaz automatického marketingu bez právního základu. Sekce B = FLOW **a Archivník** (objekty, fotky, PDF, pole). Materiálník: bez kartotéky zákazníků. |
| **Zjištění** | F1, F7, F10, F19, F20 |

### Článek III

| | |
|--|--|
| **Původní význam** | Kategorie rezervací + „evidence“; zákaz čl. 9 v poznámkách; bez telefonu/adresy/fotek. |
| **Nový význam** | Doplněny jméno, poznámka, NO-show hash; Archivník (telefon, adresa, objekty, přílohy); upozornění na čl. 6+9 u zdraví **člověka** vs. zvíře; personál včetně fotky na webu. |
| **Zjištění** | F10, F11, F15, F20 |

### Článek IV

| | |
|--|--|
| **Původní význam** | Povinnosti zpracovatele vč. incidentů a auditu. |
| **Nový význam** | Zachováno (oznámení incidentu bez zbytečného odkladu, součinnost, audit). |
| **Zjištění** | F26 — text OK; runbook stále otevřený (viz otázky) |

### Článek V

| | |
|--|--|
| **Původní význam** | Odpovědnost Správce; přístup „jen nezbytní“. |
| **Nový význam** | Doplněna odpovědnost za zákonné použití kontaktů; oprávnění = skutečné role majitel/zaměstnanec, bez tvrzení o detailním RBAC; Archivník jmenovitě. |
| **Zjištění** | F1, F7, F12 |

### Článek VI — Rezervace (A)

| | |
|--|--|
| **Původní význam** | Rezervace vzniká až e-mailovým potvrzením; Partner **nikdy** nevidí e-mail; e-mail „výhradně u Zpracovatele“. |
| **Nový význam** | Online = stav čekání + potvrzení; personál může založit bez e-mailu; Partner **vidí** kontakty pro provoz; marketing bez právního základu zakázán, systém marketing neautomatizuje. |
| **Zjištění** | F1, F2, F3, F7 |

### Článek VI — Evidence / Archivník (B)

| | |
|--|--|
| **Původní význam** | Karta jen po e-mailovém potvrzení zákazníkem; bez potvrzení nevzniká. |
| **Nový význam** | Karta zakládá Partner/personál (ručně nebo z rezervace); **bez** double opt-in; rezervace automaticky kartu nevytváří; anonymizace rezervace kartu nemaže. |
| **Zjištění** | F6, F8, F9, F12 |

### Článek VI — Fotografie / Bunny

| | |
|--|--|
| **Původní význam** | Chybělo. |
| **Nový význam** | Přílohy přes Bunny; Partner = správce rozhodnutí o souborech; Zpracovatel = zabezpečení; API vs. veřejná média webu. |
| **Zjištění** | F20, F22, F24 + Bunny kontrola níže |

### Článek VI — Materiálník

| | |
|--|--|
| **Původní význam** | Evidence materiálu + pracovníci. |
| **Nový význam** | Zachováno; upřesněno, že nejde o kartotéku zákazníků. |
| **Zjištění** | F19 |

### Článek VII

| | |
|--|--|
| **Původní význam** | E-mail Partnerovi nikdy; anonymizace do 24 h tak, že osobu nelze identifikovat; NO-show „hash“. |
| **Nový význam** | Kontakty viditelné do anonymizace; po životním cyklu (~24 h + případný děkovný mail) mazán e-mail/poznámka, mohou zůstat jméno/nick/IP; retenční cyklus ~12 měs.; NO-show = **pseudonymizovaný** hash; Archivník dlouhodobě dle účelu Partnera; zálohy 14 dní; dva samostatné výmazové nástroje Partnera. |
| **Zjištění** | F14–F18, F27, F29, doplňující analýza A/B/H |

### Článek VIII

| | |
|--|--|
| **Původní význam** | Obecný odkaz na Přílohu 3. |
| **Nový význam** | Explicitně Hetzner + Bunny; SMTP Partnera ≠ subzpracovatel Hakla; mechanismy mimo EHP zachovány. |
| **Zjištění** | F22–F24 |

### Článek IX

| | |
|--|--|
| **Původní význam** | Obecná TOM. |
| **Nový význam** | Doplněna izolace Partnerů, zálohy 14 dní, přístup Partnerových pracovníků; AI zákaz zachován. |
| **Zjištění** | F13, F17, F25, F28 |

### Článek X

| | |
|--|--|
| **Původní význam** | Součinnost u práv subjektů. |
| **Nový význam** | Partner vyřizuje žádosti; součinnost + odkaz na existující výmazové funkce (ne jedno tlačítko). |
| **Zjištění** | F27 |

### Článek XI

| | |
|--|--|
| **Původní význam** | Mlčenlivost. |
| **Nový význam** | Zachováno; výjimka výslovně zahrnuje zpřístupnění Partnerovi. |
| **Zjištění** | F1, F33 |

### Článek XII

| | |
|--|--|
| **Původní význam** | Vymazat nebo předat a vymazat (jako by proces byl hotový). |
| **Nový význam** | Povinnost dle pokynů + práva; dílčí nástroje; **neslibuje** hotový auto-offboard; účetní výjimky; zálohy dle Čl. VII. |
| **Zjištění** | F29, F30 |

---

## Kontrola konzistence

| Dokument | Výsledek |
|----------|----------|
| VOP v2.2 | Soulad: B2B, zpracovatel = Jiří Hakl, DPA jako příloha, subzpracovatelé, AI zákaz. |
| Smlouva o partnerství v2 | Soulad: Správce = Partner, DPA příloha; DPA nekoliduje s měsíčním předplatným. |
| Specifikace v2 | Soulad: START/PRO/FLOW/Materiálník/Archivník jako sjednané služby. |
| Příloha 3 – subzpracovatelé | Soulad: Hetzner + Bunny + SMTP Partnera; DPA je nyní výslovně pojmenovává. |

**K rozhodnutí vedení:** zda aktualizovat Přílohu 3 o technickou poznámku k CDN prefixu `archivnik/` (viz otevřené otázky) — DPA/VOP/Smlouvu/Specifikaci tento úkol **neměnil**.

---

## Otevřené právní / technické otázky (ke schválení)

1. **Retence ~12 měsíců** u rezervací/NO-show — potvrdit právní přiměřenost (F14–F16).  
2. **Zdravotní údaje člověka** v Archivníku (alergie v presetu) — stačí smluvní upozornění, nebo upravit produkt? (F11)  
3. **Bunny CDN — riziko veřejného prefixu `archivnik/`:**  
   - Kontrola 25. 10. 2026: CDN `haklweb.b-cdn.net` vrací **HTTP 200** pro existující objekty pod `/archivnik/ukazky/…` (veřejné marketingové snímky).  
   - Neexistující tenantové cesty vrací **404** (ne 403) → pull zone prefix `archivnik/` **obsluhuje**.  
   - Aplikace soukromé přílohy servíruje přes autentizované API; pokud by unikl `storage_key` tenantového souboru, CDN by jej mohlo vydat bez app auth.  
   - **Bez schválení konfigurace Bunny neměněna.** Doporučení: Token Auth / Edge Rule deny pro `archivnik/{tenant}/` nebo oddělená zóna (**S–M**).  
4. **Bunny DPA / SCC:** veřejná stránka `bunny.net/privacy/dpa/` → 404; Privacy policy Bunny existuje (BunnyWay d.o.o., SI). V repo **není** uložen podepsaný DPA/SCC. Doplnit interní archiv smluv.  
5. **Incident runbook** — smluvní povinnost v DPA je; provozní postup chybí (F26).  
6. **Retence Docker logů** — neověřená; nenárokovat v DPA jako fakt (F17).  
7. **Budoucí offboarding L** v Partner Adminu — schválit termín; DPA zatím neslibuje hotový tool.  
8. **Účinnost tohoto návrhu** — datum a „platné znění“ až po schválení.

---

## Finální doladění (po b170970)

| Bod | Úprava |
|-----|--------|
| A Fotografie | VI.13–14: Partner = právní důvod pořízení/uložení/zveřejnění; Zpracovatel = TOM; rozlišení interních příloh Archivníku (API) vs. veřejných médií webu (CDN). **Bez** tvrzení o nemožnosti přístupu přes CDN. |
| B Uchování | VII.3–4, 6, 8: výslovně neúplná anonymizace do 24 h; oddělení rezervací vs. Archivník; zálohy přetrvají omezeně dle retenční politiky (14 dní). |
| C Výmaz / konec | VII.9 zachován; XII.3–4: předání/výmaz na žádost Partnera; bez slibu automatického kompletního offboardingu. |
| D Zvláštní kategorie | III: Partner odpovídá za zákonnost včetně zdraví člověka; systém technicky nevylučuje vložení. |
| Meta | Stav „finální znění — ke schválení před LIVE“; Čl. XIII/7. |

**Návaznost:** VOP v2.2, Smlouva v2, Specifikace v2 — bez rozporu; jejich obchodní text neměněn.

## Potvrzení rozsahu

- Změněn pouze `modernik/dpa.html` (+ tento changelog).  
- Neměněno: rezervace/anonymizace, Archivník kód, FLOW, Materiálník, VOP, Smlouva, Specifikace, Bunny config, LIVE.  
- Staging deploy: dle pipeline z `origin/dev` po pushi.  
- LIVE: až po výslovném schválení vedením.
