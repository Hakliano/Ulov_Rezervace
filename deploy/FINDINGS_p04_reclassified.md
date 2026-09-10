# P0.4 reclassified — veřejný HTML admin drawer

**Stav:** reclassified, **neopravené**.  
**Datum:** 2026-09-10  
**Původní zařazení:** P0 (veřejný crawler vidí administraci v HTML demo webů).

## Proč to už není P0 incident

P0.1–P0.3 zavřely cesty s přímým bezpečnostním dopadem (globální admin bypass, únik interních polí z `/rezervace/info/`, plaintext SMTP v DB).

U původního P0.4 **neplatí**:

- anonymní čtení neveřejných dat z API,
- anonymní zápis do administrace,
- únik SMTP hesla v HTML.

Zůstává **information disclosure**: nginx posílá anonymovi celý admin drawer (CSS-hidden) včetně technických hintů. To je varianta „skrytí ve frontendu“, ne „server administraci nepošle“.

**V auditu musí zůstat viditelné, že veřejný HTML admin strukturu stále obsahuje.** Tento soubor to drží. Není to uzavřené bezpečnostní opatření.

## Rozdělení

| ID | Název | Priorita | Stav |
|----|--------|----------|------|
| P1 | Public admin information disclosure / cleanup | S | návrh, neimplementováno |
| P2 | Web administration architecture (admin mimo veřejný web, správa z FLOW) | product/arch | budoucí, ne hotfix |

L/XL změna architektury se jako P0.4 **nedělá**.

---

## P1 — návrh rozsahu (S)

**Cíl:** z veřejné statiky pryč zbytečné interní hinty. Admin drawer, ⚙ a přihlášení **zůstávají**.

**Mimo rozsah P1:** názvy záložek, labely polí, existence SMTP/IMAP formuláře, login form, `API_BASE` přepínač localhost:8000 (lokální vývoj). FLOW `index.html` politika hesla je mimo partnerský web — případně samostatně.

### Pryč / nahradit neutrálním textem

1. **localhost v HTML** — `Pro lokální test: http://localhost:5500…`, `Lokálně: http://localhost:5502…`, placeholder `:5503`.  
   Soubory: většina z 19 `index.html` (mimo jiné salon1–4, vertikály, Fraňek). salon3/4 mají localhost i v `placeholder` URL rezervací.
2. **Forpsi placeholdery** — `smtp.forpsi.com`, `imap.forpsi.com` ve všech 19 `index.html`.  
   Nahradit prázdným placeholderem nebo obecným „SMTP server“ / „IMAP server“.
3. **Demo e-mail** — salon3 `ahoj@crazy-hair.cz` → stejné generické `info@vase-domena.cz` jako jinde.
4. **Sdílení SMTP/IMAP credentials** — hint *„Stejné přihlášení jako SMTP.“*  
   Nechat jen že FLOW Mail čte schránku, bez vazby na SMTP heslo.
5. **Password policy + sdílené heslo web+FLOW**  
   - `shared/owner-flow-admin.js` (zdroj pravdy, injektuje záložku Heslo na weby bez vlastního panelu)  
   - duplicitní copy v `salon2/index.html`  
   Veřejně stačí „Změna hesla majitele.“ Pravidla nechat v backend validaci / chybě API po pokusu o uložení.
6. **Veřejný JS fallback** — `app.js` u dem: `smtp.forpsi.com`, `imap.forpsi.com`, `defaultRezervaceUrl()` → `http://localhost:{5499+id}/rezervace.html`.  
   Po loginu plnit jen data z API; prázdný fallback, URL rezervací z `location.origin + '/rezervace.html'` bez čísel vývojových portů.

Backend default `smtp.forpsi.com` v `get_email_config` do P1 **nesahat** (není v anonymním HTML).

### Očekávaný diff

~19× `index.html`, ~19× `app.js`, 1× `shared/owner-flow-admin.js`. Mechanický cleanup, bez nového endpointu a bez změny permission.

---

## P2 — budoucí (ne nyní)

Prověřit, že veřejný partnerský web **nemá** administrační UI a majitel spravuje obsah webu ve FLOW.

To vyžaduje produktové rozhodnutí, owner wiring, 19 statických webů a vstup místo ⚙. Není to bezpečnostní hotfix.
