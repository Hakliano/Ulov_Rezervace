window.HULINEK_SERVICE_GROUPS = [
  [
    "Preventivní péče",
    [
      "Základní klinické vyšetření",
      "Preventivní prohlídky / programy pro štěňata, koťata, stárnoucí pacienty",
      "Veškerá očkování, antiparazitární léčba (odčervení, blechy, klíšťata)",
      "Krácení drápků"
    ]
  ],
  [
    "Laboratoř a diagnostika",
    [
      "Ultrazvukové vyšetření (sono)",
      "Odběry vzorků krve a tkání k laboratorním vyšetřením a potvrzením diagnóz",
      "Rychlé krevní testy (FIV, FIP, FeLV, hypertrofická kardiomyopatie koček, parvoviróza, dirofilarióza, ehrlichióza, borelióza, anaplazmóza)",
      "Podrobné vyšetření moči (hustota, sediment, mikroskopie)",
      "Rentgenodiagnostika onemocnění (nativní i kontrastní) s digitálním RTG",
      "Biochemické vyšetření krve na vlastním přístroji IDEXX, hematologické vyšetření krve",
      "Diagnostika příčin kulhání",
      "Diagnostika, prevence a terapie poruch růstu",
      "RTG při dysplazii kyčelních, ramenních a loketních kloubů"
    ]
  ],
  [
    "Interní medicína",
    [
      "Léčba celkových i orgánových onemocnění",
      "Infuzní terapie (nitrožilní výživa a zavodnění), chemoterapie — léčba nádorů",
      "Léčba dlouhodobě nemocných pacientů",
      "Dietoterapie",
      "Léčba epilepsie, poruch chování, reprodukce a kožních onemocnění přírodními preparáty",
      "Podpůrná léčba geriatrických pacientů",
      "Podpůrná léčba pacientů s nádorovým onemocněním",
      "Využívání preparátů společnosti Energy podle pentagramu",
      "Používání přírodních přípravků s účinky antibiotik bez vedlejších efektů"
    ]
  ],
  [
    "Chirurgie",
    [
      "Gynekologické operace (císařské řezy)",
      "Léčba zlomenin (fixační obvazy, sádry, osteosyntéza)",
      "Amputace",
      "Odstranění novotvarů",
      "Chirurgické operace očních víček, ušních boltců",
      "Urologické operace (odstranění močových kamenů, řešení obstrukcí močových cest)",
      "Operace zažívacího aparátu (neprůchodnost střev)",
      "Kastrace samců a samic",
      "Kastrace (psi, kočky, králíci, morčata; samice i samci)",
      "Náhrady zkřížených vazů",
      "Chirurgické řešení luxace pately",
      "Intraartikulární aplikace léčiv při dlouhodobých potížích",
      "Diagnostika a chirurgická léčba pohlavního aparátu a mléčných žláz"
    ]
  ],
  [
    "Stomatologie",
    [
      "Extrakce zubů",
      "Odstranění zubního kamene ultrazvukem",
      "Léčba paradentózy",
      "Chirurgické zákroky na měkkých tkáních dutiny ústní (epulis, novotvary, cysty slinných žláz)"
    ]
  ],
  [
    "Dermatologie",
    [
      "Základní vyšetření kůže a kožních derivátů",
      "Mikroskopie chlupů, kožních seškrabů a stěrů",
      "Biopsie",
      "Konzultační hodiny dermatologa a kosmetická poradna",
      "Veškerá antiparazitární léčba",
      "Dermatologické koupele",
      "Alergenodiagnostika a léčba alergií"
    ]
  ],
  [
    "Reprodukce a odchov",
    [
      "Diagnostika gravidity pomocí ultrazvuku",
      "Řešení případů nežádoucího nakrytí fen",
      "Komplikované porody",
      "Řešení zánětlivých stavů na pohlavních orgánech",
      "Problematika odchovu mláďat"
    ]
  ],
  [
    "Cestování a administrativa",
    [
      "Nezaměnitelné označování zvířat (tetování, čipy)",
      "Vystavování veterinárních potvrzení pro cestování se psy, kočkami a fretkami",
      "Stanovení titru protilátek proti vzteklině",
      "Vystavování cestovních dokladů (pasporty)",
      "Vedení předepsané evidence cestovních dokladů",
      "Konzultace náležitostí při cestování se zvířaty do zahraničí",
      "Vyšetření zvířete, které poranilo člověka, a vystavení dokladu o výsledku vyšetření"
    ]
  ],
  [
    "Výživa a prodej",
    [
      "Konzultace způsobů krmení psů, koček a ostatních domácích mazlíčků",
      "Nabídka kvalitních krmiv a veterinárních terapeutických diet",
      "E-shop krmiv Specific s výhodnými cenami pro zaregistrované",
      "Prodej veškerých veterinárních léčiv"
    ]
  ],
  [
    "Anestezie a další péče",
    [
      "Anesteziologie (zklidnění, léčba bolesti a celková narkóza)",
      "Účinná léčba bolesti",
      "Využívání totální intravenózní anestezie (TIVA) u rizikových pacientů",
      "Konzultace poruch chování",
      "Konzultace po telefonu"
    ]
  ]
];

window.groupHulinekServices = function (items) {
  const list = items || [];
  const byName = new Map(list.map((item) => [item.nazev, item]));
  const used = new Set();
  const groups = [];
  for (const [title, names] of (window.HULINEK_SERVICE_GROUPS || [])) {
    const rows = names.map((name) => byName.get(name)).filter(Boolean);
    rows.forEach((item) => used.add(item.nazev));
    if (rows.length) groups.push([title, rows]);
  }
  const rest = list.filter((item) => !used.has(item.nazev));
  if (rest.length) groups.push(['Další služby', rest]);
  return groups;
};

