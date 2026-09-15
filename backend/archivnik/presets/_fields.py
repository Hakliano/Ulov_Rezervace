"""Sdílené volby a zkratky pro katalog presetů."""

POHLAVI = ['Samec', 'Samice', 'Neurčeno']
VLASY_TYP = ['Rovné', 'Vlnité', 'Kudrnaté', 'Afro']
VLASY_JEMNOST = ['Jemné', 'Střední', 'Hrubé']
VLASY_HUSTOTA = ['Řídké', 'Střední', 'Husté']
VLASY_DELKA = ['Krátké', 'Střední', 'Dlouhé', 'Extra dlouhé']
VLASY_STAV = ['Zdravé', 'Suché', 'Poškozené', 'Barvené']
VOUSY_HUSTOTA = ['Řídké', 'Střední', 'Husté']
PLET_TYP = ['Suchá', 'Mastná', 'Smíšená', 'Citlivá', 'Normální']
PLET_PODTON = ['Studený', 'Teplý', 'Neutrální']
POHON = ['FWD', 'RWD', 'AWD', '4×4']


def f(nazev, druh, volby=None):
    return {'nazev': nazev, 'druh': druh, 'volby': list(volby or [])}


def t(nazev, pole, vyzaduje_nazev=True):
    return {'nazev': nazev, 'pole': list(pole), 'vyzaduje_nazev': vyzaduje_nazev}
