# Zdroj kalendáře jmenin (Pošťák)

Pošťák používá **lokální** soubor `jadro/data/jmeniny_cz.json` (kopie ve `static/jmeniny_cz.json` pro přehled v prohlížeči).

Data vycházejí z přehledu **jmenin v Česku** podle civilního občanského kalendáře z přelomu 80./90. let (jak ho shrnuje Wikipedie v článku [Jmeniny v Česku](https://cs.wikipedia.org/wiki/Jmeniny_v_%C4%8Cesku), sekce „Podle data“, doplněno o chybějící dny z abecedního rejstříku ve stejném článku).

- Jedná se o **jmeniny**, ne o státní svátky (1. 1., velikonoce, 1. 5., 28. 10., 24.–26. 12. atd. v kalendáři typicky nemají přiřazené jméno).
- Více jmen v jeden den je zachováno (např. 5. 2. Dobromila, Dobromíra).
- **29. únor**: Horymír.

Kalendář se na serveru i v banneru vyhodnocuje v pásmu `Europe/Prague` (viz `TIME_ZONE` v Django).
