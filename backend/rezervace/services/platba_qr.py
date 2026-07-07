"""QR platba – český formát SPAYD pro bankovní aplikace."""

import io
import re


def normalize_ucet(ucet):
    """Vrátí hodnotu pro pole ACC ve SPAYD (IBAN nebo číslo/banka)."""
    u = (ucet or '').strip().replace(' ', '')
    if not u:
        raise ValueError('Číslo účtu je povinné.')
    if u.upper().startswith('CZ'):
        return u.upper()
    if '/' in u:
        return u
    if re.match(r'^\d+$', u):
        raise ValueError('Zadejte účet ve formátu číslo/kód banky nebo IBAN (CZ…).')
    return u


def spayd_string(ucet, castka, variabilni_symbol, zprava=''):
    acc = normalize_ucet(ucet)
    try:
        amount = float(str(castka).replace(',', '.').replace(' ', ''))
    except (TypeError, ValueError):
        raise ValueError('Neplatná částka.')
    if amount <= 0:
        raise ValueError('Částka musí být větší než 0.')
    vs = str(variabilni_symbol or '').strip()
    if not vs.isdigit():
        raise ValueError('Variabilní symbol musí být číslo.')
    parts = [
        'SPD*1.0',
        f'ACC:{acc}',
        f'AM:{amount:.2f}',
        'CC:CZK',
        f'X-VS:{vs}',
    ]
    msg = (zprava or '').strip()[:60]
    if msg:
        parts.append(f'MSG:{msg}')
    return '*'.join(parts)


def qr_png_bytes(spayd):
    import qrcode

    qr = qrcode.QRCode(version=None, box_size=8, border=2)
    qr.add_data(spayd)
    qr.make(fit=True)
    img = qr.make_image(fill_color='black', back_color='white')
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


def generuj_platbu_qr(ucet, castka, variabilni_symbol, zprava=''):
    """Vrátí SPAYD, PNG a formátované údaje pro e-mail i zobrazení na obrazovce."""
    amount = float(str(castka).replace(',', '.').replace(' ', ''))
    spayd = spayd_string(ucet, amount, variabilni_symbol, zprava=zprava)
    qr_png = qr_png_bytes(spayd)
    return {
        'spayd': spayd,
        'qr_png': qr_png,
        'castka': amount,
        'castka_display': f'{amount:,.0f}'.replace(',', '\u00a0'),
        'ucet': ucet.strip(),
        'variabilni_symbol': str(variabilni_symbol).strip(),
    }
