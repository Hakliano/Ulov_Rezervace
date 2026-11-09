"""IMAP akce: přečteno, koš, obnova."""

from __future__ import annotations

import re

from .mail_imap import MailError, _safe_folder, imap_session, list_folders

TRASH_HINTS = ('trash', 'kos', 'koš', 'deleted', 'smazan')
SENT_HINTS = ('sent', 'odesl', 'odeslan')


def _match_folder(names, hints):
    for name in names:
        low = name.lower()
        if any(h in low for h in hints):
            return name
    return ''


def trash_folder(schranka):
    names = [f['name'] for f in list_folders(schranka)]
    found = _match_folder(names, TRASH_HINTS)
    if not found:
        raise MailError('Složku Koš na serveru nelze najít.')
    return found


def sent_folder(schranka):
    names = [f['name'] for f in list_folders(schranka)]
    return _match_folder(names, SENT_HINTS) or 'Sent'


def is_trash_folder(schranka, folder: str) -> bool:
    try:
        return _safe_folder(folder) == _safe_folder(trash_folder(schranka))
    except MailError:
        return False


def set_seen(schranka, *, folder, uid, seen: bool):
    folder = _safe_folder(folder)
    uid = int(uid)
    with imap_session(schranka) as client:
        client.select(folder, readonly=False)
        action = '+FLAGS' if seen else '-FLAGS'
        typ, _ = client.uid('STORE', str(uid), action, r'(\Seen)')
        if typ != 'OK':
            raise MailError('Stav přečtení nelze uložit.')


def move_to_trash(schranka, *, folder, uids):
    folder = _safe_folder(folder)
    trash = trash_folder(schranka)
    if folder == trash:
        raise MailError('Zpráva už je v koši.')
    uids = [int(u) for u in uids if str(u).isdigit()]
    if not uids:
        raise MailError('Nejsou vybrané žádné zprávy.')
    with imap_session(schranka) as client:
        client.select(folder, readonly=False)
        for uid in uids:
            typ, _ = client.uid('COPY', str(uid), trash)
            if typ != 'OK':
                raise MailError(f'Zprávu {uid} nelze přesunout do koše.')
            typ, _ = client.uid('STORE', str(uid), '+FLAGS', r'(\Deleted)')
            if typ != 'OK':
                raise MailError(f'Zprávu {uid} nelze označit ke smazání.')
        client.expunge()


def restore_messages(schranka, *, folder, uids, target='INBOX'):
    folder = _safe_folder(folder)
    trash = trash_folder(schranka)
    if folder != trash:
        raise MailError('Obnova je jen ze složky Koš.')
    uids = [int(u) for u in uids if str(u).isdigit()]
    target = _safe_folder(target)
    with imap_session(schranka) as client:
        client.select(folder, readonly=False)
        for uid in uids:
            typ, _ = client.uid('COPY', str(uid), target)
            if typ != 'OK':
                raise MailError(f'Zprávu {uid} nelze obnovit.')
            typ, _ = client.uid('STORE', str(uid), '+FLAGS', r'(\Deleted)')
            if typ != 'OK':
                raise MailError(f'Zprávu {uid} nelze odstranit z koše.')
        client.expunge()


def delete_permanent(schranka, *, folder, uids):
    folder = _safe_folder(folder)
    if not is_trash_folder(schranka, folder):
        raise MailError('Trvalé smazání je povolené jen v koši.')
    uids = [int(u) for u in uids if str(u).isdigit()]
    with imap_session(schranka) as client:
        client.select(folder, readonly=False)
        for uid in uids:
            typ, _ = client.uid('STORE', str(uid), '+FLAGS', r'(\Deleted)')
            if typ != 'OK':
                raise MailError(f'Zprávu {uid} nelze smazat.')
        client.expunge()
