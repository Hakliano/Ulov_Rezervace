# Telefonní klikačka – podklady pro obsah scénářů (JSON)

**Verze:** 2026-03-13  
**Prostředí:** pouze LOCAL Pošťák  
**Ukázkový soubor:** `phone_scripts/fixtures/demo-modernik.export.json` (export z publikovaného `demo-modernik`)

Tento dokument popisuje formát JSON pro přípravu skutečných obchodních scénářů **Moderník** a **HereYouAre**. Technická klikátka (připravit → START → lokální přechody) zůstává beze změny.

---

## 1. Přehled struktury souboru

| Kořenový klíč | Účel |
|---------------|------|
| `meta` | Identifikace scénáře (slug, název, produkt). |
| `initialBranches` | Mapování **6 vstupních kombinací** → `step_id` prvního kroku po START. |
| `openings` | Volitelné úvodní oslovení (proměnná `{agent_name}`). |
| `areas` | Tematické oblasti pro přeskok „Jiná oblast“. |
| `steps` | Graf rozhovoru – hlavní obsah. |
| `objections` | Knihovna námitek. |
| `pricing` | Řádky ceníku (referenční texty v krocích). |

**Princip:** jeden scénář = **jeden produkt** (`modernik` nebo `hereyouare`). Nejde o 12 samostatných souborů – jeden graf sdílí většinu kroků, liší se hlavně **vstupní větve** podle webu a stylu prodeje.

---

## 2. `meta`

```json
{
  "meta": {
    "slug": "demo-modernik",
    "name": "Demo Moderník",
    "product": "modernik"
  }
```

| Pole | Povinné | Hodnoty |
|------|---------|---------|
| `slug` | ano | Jedinečný identifikátor v DB, např. `modernik`, `modernik-obsah-v1` (ne přepisovat `demo-modernik` bez vědomého `--replace`). |
| `name` | ano | Lidský název v UI. |
| `product` | ano | `modernik` nebo `hereyouare` |

Pole `version` v exportu odráží publikovanou verzi – při ruční editaci JSON **nemusíte** verzi řešit; vznikne až při publikaci v adminu.

---

## 3. Vstupní větve `initialBranches`

Klíče **musí být přesně tyto** (složenina stavu webu + stylu):

| Klíč | Význam |
|------|--------|
| `has_web_calm` | Má web, klidný prodej |
| `has_web_dynamic` | Má web, dynamický prodej |
| `no_web_calm` | Nemá web, klidný |
| `no_web_dynamic` | Nemá web, dynamický |
| `unknown_calm` | Neznámý stav webu, klidný |
| `unknown_dynamic` | Neznámý stav webu, dynamický |

Hodnota je `step_id` vstupního kroku (řetězec).

**Ukázka z dema:** šest různých vstupních kroků (`entry_has`, `entry_has_dyn`, …), které po jedné odpovědi **sjednotí** tok na společný krok `uvod_1`.

```json
"initialBranches": {
  "has_web_calm": "entry_has",
  "has_web_dynamic": "entry_has_dyn",
  "no_web_calm": "entry_no",
  "no_web_dynamic": "entry_no_dyn",
  "unknown_calm": "entry_unk",
  "unknown_dynamic": "entry_unk_dyn"
}
```

---

## 4. Tematické oblasti `areas`

Objekt: klíč = `slug` oblasti.

| Pole | Povinné | Popis |
|------|---------|--------|
| `slug` | ano | Stabilní ID (např. `rezervace`, `archivnik`). |
| `name` | ano | Název v selectu „Jiná oblast“. |
| `sortOrder` | doporučeno | Pořadí v seznamu (celé číslo). |
| `entryStepId` | doporučeno | Krok, na který skočí přeskok oblasti. |

Oblast odkazují kroky přes `areaSlug` u jednotlivých kroků.

---

## 5. Kroky `steps`

Objekt: klíč = **`step_id`** (jedinečné v rámci scénáře, např. `rez_1`, doporučení: `snake_case`, bez mezer).

| Pole | Povinné | Hodnoty / poznámka |
|------|---------|---------------------|
| `type` | ano* | Viz tabulka typů níže (*import doplní `question`, pokud chybí). |
| `say` | ano | Věta pro telefonistu. Podporuje `{agent_name}`. |
| `goal` | ne | Interní „Cíl otázky“ (nezobrazí se zákazníkovi). |
| `areaSlug` | ne | Navázání na oblast z `areas`. |
| `answers` | u `question` ano | Pole možných odpovědí zákazníka. |

### Typy kroků (`type`)

| Hodnota | Význam |
|---------|--------|
| `question` | Otázka s odpověďmi (hlavní typ). |
| `info` | Informace s navazující odpovědí. |
| `pricing` | Cenová / nabídková pasáž. |
| `closing` | Přirozený závěr hovoru. |
| `polite_exit` | Zdvořilé ukončení (odmítnutí rozhovoru). |

### Odpověď zákazníka (`answers[]`)

| Pole | Popis |
|------|--------|
| `label` | Text na tlačítku. |
| `sortOrder` | Pořadí (0, 1, 2…). |
| `targetStepId` | Další krok v grafu. |
| `endCall` | `true` = ukončení hovoru (bez dalšího kroku). |
| `jumpAreaSlug` | Místo cílového kroku přeskočit na vstup oblasti (pokročilé). |

**Pravidlo:** každá odpověď musí mít buď `targetStepId`, nebo `endCall: true`, nebo `jumpAreaSlug` (vázané na existující oblast).

Při **exportu** z Pošťáka mohou odpovědi obsahovat i pole `id` – import je ignoruje.

---

## 6. Klidný vs. dynamický prodej – jak psát obsah

Cíl zadání: **odlišné formulace**, **společný střed grafu**.

### Doporučený vzor (jako v demu)

1. **Vstupní kroky (6 větví):**  
   - 3 varianty podle webu (`has` / `no` / `unknown`) × 2 texty (klidný × dynamický) = až **6 samostatných `step_id`**.  
   - Klidný: delší, měkčí věty, v demu např. *„Půjdeme na to v klidu krok za krokem.“*  
   - Dynamický: kratší, přímější, v demu např. *„Půjdeme na to přímo.“*

2. **Spojení:** každý vstupní krok má typicky **jednu** odpověď („Pokračovat“) → **`targetStepId`** na **společný** krok (v demu `uvod_1`).

3. **Dál v grafu:** stejné kroky pro oba styly, **pokud** obchodně dává smysl. Kde má dynamický styl kratší variantu otázky, vytvořte dvě větve (`probe_calm_1` / `probe_dyn_1`), které se zase **sloučí** na další společný uzel.

4. **Neměnit pouze UI** – rozdíl musí být v `say` (a případně v délce / počtu mezikroků), ne v barvách obrazovky.

### NAMING convention (doporučení pro obsah)

| Suffix / prefix | Význam |
|-----------------|--------|
| `entry_*` | Vstupy z `initialBranches`. |
| `*_dyn` nebo `dynamic` v `step_id` | Dynamická varianta párového kroku. |
| bez suffixu nebo `_calm` | Klidná varianta. |

---

## 7. Námitky `objections`

Objekt: klíč = `slug` námitky (např. `drahe`, `nemám_cas`).

| Pole | Popis |
|------|--------|
| `title` | Název v seznamu námitek. |
| `sortOrder` | Pořadí v menu. |
| `rootStepId` | Volitelně: podgraf otázek po výběru námitky (viz „Je to drahé“ v demu → `obj_price`). |
| `responses` | Rychlé reakce telefonisty. |

### `responses[]`

| Pole | Popis |
|------|--------|
| `say` | Co říct zákazníkovi. |
| `sortOrder` | Pořadí. |
| `hardReject` | `true` = výslovný zákaz kontaktu → ukončení hovoru v UI. |
| `returnOnly` | `true` = po přečtení zavřít námitku a vrátit se na původní krok (výchozí u jednoduchých reakcí). |
| `targetStepId` | Po reakci pokračovat jiným krokem v hlavním grafu. |

**Varování validace:** kroky používané **jen** z námitek (např. `obj_price`) mohou při publikaci vyvolat **varování** o nedosažitelnosti z hlavních větví – to je u podgrafů námitek **přípustné**.

---

## 8. Ceník `pricing`

Pole objektů (informace pro tvorbu textů v krocích typu `pricing`):

| Pole | Povinné |
|------|---------|
| `productName` | ano |
| `monthlyCzk` | ano (číslo) |
| `activationCzk` | ano (číslo) |
| `description` | ne |
| `sortOrder` | doporučeno |

---

## 9. Validace před publikací

Publikace (`Publikovat` v Django Admin nebo `import … --publish`) spustí kontrolu. **Bez úspěchu se scénář neaktivuje.**

| Kontrola | Chyba (blokuje) |
|----------|------------------|
| Všechny cíle `targetStepId` existují ve stejném scénáři | ano |
| Každá odpověď má cíl, `endCall`, nebo skok oblasti | ano |
| Všech **6** klíčů v `initialBranches` | ano |
| Otázka (`question`) má alespoň jednu odpověď | ano |
| Alespoň jedno ukončení (`closing` / `polite_exit` / odpověď s `endCall`) | ano |
| Nedosažitelné kroky z větví | **varování** (u námitek obvykle OK) |

---

## 10. Bezpečný import (nepřepsat demo)

### Doporučený postup pro nový obsah Moderník

1. V JSON nastavte **nový slug**, např. `modernik` nebo `modernik-obsah-2026-03` (v `meta.slug`).
2. **`product`** ponechte `modernik`.
3. Import **bez** `--replace`:

   ```powershell
   cd c:\Users\Jirka\Projekty\weby_s_externi_DTB\postak
   python manage.py import_phone_script sciezky\modernik-obsah.json
   ```

   Scénář `demo-modernik` zůstane nedotčený.

4. Kontrola parsování (neukládá do DB struktury kroků – jen JSON syntax + počet kroků):

   ```powershell
   python manage.py import_phone_script sciezky\modernik-obsah.json --dry-run
   ```

5. Po obsahové kontrole v adminu: akce **Publikovat** – teprve pak vznikne `published_snapshot` a verze.

6. **Až budete chtít nahradit starý obsah stejného slugu:** explicitně `--replace` (smaže kroky daného slugu a znovu naimportuje).

### Export / záloha před změnami

```powershell
python manage.py export_phone_script demo-modernik -o zaloha\demo-modernik.json
python manage.py export_phone_script modernik -o zaloha\modernik.json
```

### Důležité: jeden aktivní scénář na produkt v UI

V přípravné obrazovce klikačka vybírá scénář takto: **první aktivní záznam** s daným `product` v seznamu z API. Pokud budou **zároveň aktivní** `demo-modernik` i `modernik`, může se načíst neočekávaný scénář.

**Pro testování nového obsahu na LOCAL:**

- buď **deaktivujte** `demo-modernik` v adminu (`is_active=False`) a aktivní nechte jen nový `modernik`,  
- nebo ponechte demo neaktivní po přepnutí na produkční slug.

---

## 11. Rozsah 150–200 kroků – omezení importéru

| Oblast | Stav |
|--------|------|
| Velikost JSON | Řádově stovky kroků jsou v pořádku (typicky &lt; 1 MB). |
| Import | Jeden soubor, jedna transakce – celý scénář najednou. |
| `--dry-run` | Ověří jen **platný JSON** a **počet kroků**, ne celou validaci grafu. Plnou validaci až **publikace** nebo admin „Zkontrolovat“. |
| Duplicitní `step_id` | Import selže (unikátnost v rámci scénáře). |
| Ruční `id` u odpovědí z exportu | Lze nechat, import je nepotřebuje. |
| Cykly v grafu | Povolené (záměrné návraty); validátor nekontroluje nekonečné smyčky. |
| Úpravy po importu | Admin nebo nový import s `--replace`. |
| Výkon po publikaci | Beze změny – snapshot se načte jednou do prohlížeče. |

Žádné známé **tvrdé omezení** počtu kroků v importéru; projektově otestováno se scénářem `stress-test` (180+ kroků).

---

## 12. Šablona minimálního nového souboru

Pro start kopírujte `demo-modernik.export.json`, změňte `meta.slug` / `meta.name`, doplňte oblasti a kroky podle kapitol zadání (Moderník 8 oblastí). HereYouAre = stejný formát, `product: "hereyouare"`.

---

## 13. Kontakt na technické soubory v repu

| Soubor | Účel |
|--------|------|
| `phone_scripts/fixtures/demo-modernik.export.json` | Aktuální export dema |
| `phone_scripts/demo_content.py` | Zdroj dema (referenční logika větví) |
| `phone_scripts/services/import_export.py` | Pravidla importu |
| `phone_scripts/services/validate.py` | Validace před publikací |

---

*Po dokončení obsahu dodáte JSON → LOCAL import → publikace → uživatelské testování všech 6 vstupních kombinací.*
