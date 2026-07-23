"""QR platba – český formát SPAYD pro bankovní aplikace."""

import io
import re


def _czech_national_to_iban(ucet: str) -> str:
    """Převede číslo/kód banky (vč. předčíslí) na IBAN CZ…"""
    u = ucet.strip().replace(' ', '')
    if '/' not in u:
        raise ValueError('Zadejte účet ve formátu číslo/kód banky nebo IBAN (CZ…).')
    left, bank = u.rsplit('/', 1)
    bank = bank.strip()
    if not re.fullmatch(r'\d{4}', bank):
        raise ValueError('Kód banky musí mít 4 číslice (např. 3030).')
    if '-' in left:
        prefix, number = left.split('-', 1)
    else:
        prefix, number = '', left
    prefix = prefix.strip()
    number = number.strip()
    if prefix and not re.fullmatch(r'\d{1,6}', prefix):
        raise ValueError('Neplatné předčíslí účtu.')
    if not re.fullmatch(r'\d{1,10}', number):
        raise ValueError('Neplatné číslo účtu.')
    # BBAN = kód banky (4) + předčíslí (6) + číslo (10)
    bban = f'{bank}{prefix.zfill(6)}{number.zfill(10)}'
    # Kontrolní číslice IBAN (CZ = 12 35)
    check = 98 - (int(bban + '123500') % 97)
    return f'CZ{check:02d}{bban}'


def normalize_ucet(ucet):
    """Vrátí IBAN pro pole ACC ve SPAYD (bankovní appky vyžadují IBAN, ne číslo/banka)."""
    u = (ucet or '').strip().replace(' ', '')
    if not u:
        raise ValueError('Číslo účtu je povinné.')
    if u.upper().startswith('CZ'):
        iban = u.upper()
        if not re.fullmatch(r'CZ\d{22}', iban):
            raise ValueError('Neplatný IBAN (očekáváno CZ + 22 číslic).')
        # ověření kontrolních číslic
        rearr = iban[4:] + ''.join(
            str(ord(c) - 55) if c.isalpha() else c for c in iban[:4]
        )
        if int(rearr) % 97 != 1:
            raise ValueError('Neplatný IBAN (špatná kontrolní číslice).')
        return iban
    if '/' in u:
        return _czech_national_to_iban(u)
    if re.match(r'^\d+$', u):
        raise ValueError('Zadejte účet ve formátu číslo/kód banky nebo IBAN (CZ…).')
    raise ValueError('Neplatné číslo účtu.')


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
    msg = (zprava or '').strip()[:60].replace('*', ' ')
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
    iban = normalize_ucet(ucet)
    spayd = spayd_string(ucet, amount, variabilni_symbol, zprava=zprava)
    qr_png = qr_png_bytes(spayd)
    return {
        'spayd': spayd,
        'qr_png': qr_png,
        'castka': amount,
        'castka_display': f'{amount:,.0f}'.replace(',', '\u00a0'),
        'ucet': (ucet or '').strip(),
        'iban': iban,
        'variabilni_symbol': str(variabilni_symbol).strip(),
    }
