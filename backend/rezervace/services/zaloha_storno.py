"""Texty o záloze při stornu — vztah zákazník ↔ partner (provozovna)."""


def zaloha_je_zaplacena(rezervace) -> bool:
    return bool(getattr(rezervace, 'zaloha_ok_at', None))


def kontakt_provozovny(salon) -> str:
    phone = (getattr(salon, 'phone', None) or '').strip()
    if phone:
        return phone
    email = (getattr(salon, 'email', None) or '').strip()
    if email:
        return email
    return 'kontaktní údaje na webu provozovny'


def zaloha_castka_txt(rezervace) -> str:
    castka = getattr(rezervace, 'zaloha_castka', None)
    if castka is None:
        return ''
    return f'{castka} Kč'


def email_blok_zaloha(rezervace, kdo: str = 'zákazník') -> str:
    """Blok do e-mailu storna — jen když partner potvrdil přijetí zálohy."""
    if not zaloha_je_zaplacena(rezervace):
        return ''
    salon = rezervace.salon
    kontakt = kontakt_provozovny(salon)
    castka = zaloha_castka_txt(rezervace)
    castka_vet = f' ve výši {castka}' if castka else ''
    salon_kdo = kdo in ('salon', 'admin', 'flow')

    if salon_kdo:
        return (
            '--------------------\n'
            'ZÁLOHA\n'
            f'Na tuto službu byla řádně zaplacena záloha{castka_vet}.\n'
            f'Prosím zavolejte na {kontakt}, abychom se domluvili, zda zálohu '
            'přesuneme na jiný termín, nebo ji vrátíme a jakým způsobem.\n'
            '--------------------'
        )
    return (
        '--------------------\n'
        'ZÁLOHA\n'
        f'Na tuto službu byla řádně zaplacena záloha{castka_vet}.\n'
        f'Prosím zavolejte na telefonní číslo {kontakt}, kde se domluvíte, '
        'zda se záloha přesune na jiný termín, nebo bude vrácena a jak.\n'
        '--------------------'
    )


def storno_zaloha_payload(rezervace, lze_stornovat: bool) -> dict:
    """Data pro storno info API / stránku."""
    if not zaloha_je_zaplacena(rezervace):
        return {
            'zaloha_zaplacena': False,
            'zaloha_castka': None,
            'zaloha_info': '',
            'zaloha_propada': False,
        }
    salon = rezervace.salon
    kontakt = kontakt_provozovny(salon)
    castka = zaloha_castka_txt(rezervace)
    castka_vet = f' ve výši {castka}' if castka else ''

    if lze_stornovat:
        info = (
            f'Na tuto službu byla řádně zaplacena záloha{castka_vet}. '
            f'Po zrušení termínu prosím zavolejte na {kontakt} a domluvte se s provozovnou, '
            'zda se záloha přesune na jiný termín, nebo bude vrácena a jak.'
        )
        return {
            'zaloha_zaplacena': True,
            'zaloha_castka': str(rezervace.zaloha_castka) if rezervace.zaloha_castka is not None else None,
            'zaloha_info': info,
            'zaloha_propada': False,
        }

    info = (
        f'Na tuto službu byla řádně zaplacena záloha{castka_vet}. '
        'Storno mimo povolenou lhůtu není možné — záloha propadá. '
        f'Dotazy řešte telefonicky s provozovnou: {kontakt}.'
    )
    return {
        'zaloha_zaplacena': True,
        'zaloha_castka': str(rezervace.zaloha_castka) if rezervace.zaloha_castka is not None else None,
        'zaloha_info': info,
        'zaloha_propada': True,
    }
