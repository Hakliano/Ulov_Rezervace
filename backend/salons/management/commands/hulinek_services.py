"""Služby dema Veterina Hulínek — ceny v DB mohou být, na webu se nesvětlí."""

HULINEK_GROUPS = [
    (
        'Preventivní péče',
        [
            ('Základní klinické vyšetření', 30),
            ('Preventivní prohlídky / programy pro štěňata, koťata, stárnoucí pacienty', 40),
            ('Veškerá očkování, antiparazitární léčba (odčervení, blechy, klíšťata)', 20),
            ('Krácení drápků', 15),
        ],
    ),
    (
        'Laboratoř a diagnostika',
        [
            ('Ultrazvukové vyšetření (sono)', 30),
            ('Odběry vzorků krve a tkání k laboratorním vyšetřením a potvrzením diagnóz', 20),
            ('Rychlé krevní testy (FIV, FIP, FeLV, hypertrofická kardiomyopatie koček, parvoviróza, dirofilarióza, ehrlichióza, borelióza, anaplazmóza)', 20),
            ('Podrobné vyšetření moči (hustota, sediment, mikroskopie)', 20),
            ('Rentgenodiagnostika onemocnění (nativní i kontrastní) s digitálním RTG', 30),
            ('Biochemické vyšetření krve na vlastním přístroji IDEXX, hematologické vyšetření krve', 25),
            ('Diagnostika příčin kulhání', 40),
            ('Diagnostika, prevence a terapie poruch růstu', 40),
            ('RTG při dysplazii kyčelních, ramenních a loketních kloubů', 30),
        ],
    ),
    (
        'Interní medicína',
        [
            ('Léčba celkových i orgánových onemocnění', 30),
            ('Infuzní terapie (nitrožilní výživa a zavodnění), chemoterapie — léčba nádorů', 60),
            ('Léčba dlouhodobě nemocných pacientů', 30),
            ('Dietoterapie', 30),
            ('Léčba epilepsie, poruch chování, reprodukce a kožních onemocnění přírodními preparáty', 30),
            ('Podpůrná léčba geriatrických pacientů', 30),
            ('Podpůrná léčba pacientů s nádorovým onemocněním', 30),
            ('Využívání preparátů společnosti Energy podle pentagramu', 30),
            ('Používání přírodních přípravků s účinky antibiotik bez vedlejších efektů', 20),
        ],
    ),
    (
        'Chirurgie',
        [
            ('Gynekologické operace (císařské řezy)', 90),
            ('Léčba zlomenin (fixační obvazy, sádry, osteosyntéza)', 60),
            ('Amputace', 60),
            ('Odstranění novotvarů', 45),
            ('Chirurgické operace očních víček, ušních boltců', 45),
            ('Urologické operace (odstranění močových kamenů, řešení obstrukcí močových cest)', 60),
            ('Operace zažívacího aparátu (neprůchodnost střev)', 60),
            ('Kastrace samců a samic', 45),
            ('Kastrace (psi, kočky, králíci, morčata; samice i samci)', 45),
            ('Náhrady zkřížených vazů', 90),
            ('Chirurgické řešení luxace pately', 60),
            ('Intraartikulární aplikace léčiv při dlouhodobých potížích', 20),
            ('Diagnostika a chirurgická léčba pohlavního aparátu a mléčných žláz', 45),
        ],
    ),
    (
        'Stomatologie',
        [
            ('Extrakce zubů', 30),
            ('Odstranění zubního kamene ultrazvukem', 40),
            ('Léčba paradentózy', 40),
            ('Chirurgické zákroky na měkkých tkáních dutiny ústní (epulis, novotvary, cysty slinných žláz)', 45),
        ],
    ),
    (
        'Dermatologie',
        [
            ('Základní vyšetření kůže a kožních derivátů', 25),
            ('Mikroskopie chlupů, kožních seškrabů a stěrů', 20),
            ('Biopsie', 20),
            ('Konzultační hodiny dermatologa a kosmetická poradna', 30),
            ('Veškerá antiparazitární léčba', 20),
            ('Dermatologické koupele', 30),
            ('Alergenodiagnostika a léčba alergií', 40),
        ],
    ),
    (
        'Reprodukce a odchov',
        [
            ('Diagnostika gravidity pomocí ultrazvuku', 20),
            ('Řešení případů nežádoucího nakrytí fen', 30),
            ('Komplikované porody', 60),
            ('Řešení zánětlivých stavů na pohlavních orgánech', 30),
            ('Problematika odchovu mláďat', 30),
        ],
    ),
    (
        'Cestování a administrativa',
        [
            ('Nezaměnitelné označování zvířat (tetování, čipy)', 20),
            ('Vystavování veterinárních potvrzení pro cestování se psy, kočkami a fretkami', 20),
            ('Stanovení titru protilátek proti vzteklině', 20),
            ('Vystavování cestovních dokladů (pasporty)', 20),
            ('Vedení předepsané evidence cestovních dokladů', 15),
            ('Konzultace náležitostí při cestování se zvířaty do zahraničí', 20),
            ('Vyšetření zvířete, které poranilo člověka, a vystavení dokladu o výsledku vyšetření', 25),
        ],
    ),
    (
        'Výživa a prodej',
        [
            ('Konzultace způsobů krmení psů, koček a ostatních domácích mazlíčků', 20),
            ('Nabídka kvalitních krmiv a veterinárních terapeutických diet', 15),
            ('E-shop krmiv Specific s výhodnými cenami pro zaregistrované', 15),
            ('Prodej veškerých veterinárních léčiv', 15),
        ],
    ),
    (
        'Anestezie a další péče',
        [
            ('Anesteziologie (zklidnění, léčba bolesti a celková narkóza)', 30),
            ('Účinná léčba bolesti', 20),
            ('Využívání totální intravenózní anestezie (TIVA) u rizikových pacientů', 40),
            ('Konzultace poruch chování', 30),
            ('Konzultace po telefonu', 10),
        ],
    ),
]


def hulinek_service_tuples():
    """(název, cena, délka) — cena 0, na webu se stejně nevypisuje."""
    rows = []
    for _title, items in HULINEK_GROUPS:
        for name, minutes in items:
            rows.append((name, 0, minutes))
    return rows


def hulinek_group_names():
    return [(title, [name for name, _m in items]) for title, items in HULINEK_GROUPS]
