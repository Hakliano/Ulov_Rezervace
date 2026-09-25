"""Zobrazení ceny služby na webu. FLOW sčítá pole cena (spodní / nula)."""


def _int_or_none(value):
    if value is None or value == '':
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def format_cenik_cena(cena, cena_do=None, zobrazit_od=False):
    """Prázdné = nic. 0 = Zdarma. Rozsah ignoruje tickbox Od."""
    a = _int_or_none(cena)
    b = _int_or_none(cena_do)
    if a is None:
        return ''
    if a == 0:
        return 'Zdarma'
    if b is not None and b != a:
        lo, hi = (a, b) if a < b else (b, a)
        return f'{lo}–{hi} Kč'
    if zobrazit_od:
        return f'Od {a} Kč'
    return f'{a} Kč'
