"""Majitelka také pracuje — pracovní persona bez druhého loginu."""

from __future__ import annotations

from datetime import time

from django.db import transaction

from flow.models import FlowUser
from rezervace.models import Zamestnanec, ZamestnanecRozvrh

# Po–Pá 9:00–17:00, So+Ne volno
_DEFAULT_OD = time(9, 0)
_DEFAULT_DO = time(17, 0)


def majitelka_pracuje_payload(flow_user: FlowUser | None) -> dict:
    if not flow_user:
        return {'ano': False, 'pracovni': None}
    pz = flow_user.pracovni_zamestnanec
    if not pz or pz.salon_id != flow_user.salon_id:
        return {'ano': False, 'pracovni': None}
    return {
        'ano': True,
        'pracovni': {
            'id': pz.id,
            'jmeno': pz.jmeno,
            'zobrazit_na_webu': pz.zobrazit_na_webu,
            'aktivni': pz.aktivni,
        },
    }


def _default_rozvrh(zam: Zamestnanec) -> None:
    """Výchozí rozvrh, pokud ještě žádný nemá (nebo jsou samá volna bez času)."""
    existing = list(zam.rozvrh.all())
    if existing:
        has_work = any(not r.volno and r.od and r.do for r in existing)
        if has_work:
            return
        zam.rozvrh.all().delete()
    for den in range(7):
        if den < 5:
            ZamestnanecRozvrh.objects.create(
                zamestnanec=zam,
                den=den,
                volno=False,
                od=_DEFAULT_OD,
                do=_DEFAULT_DO,
            )
        else:
            ZamestnanecRozvrh.objects.create(
                zamestnanec=zam,
                den=den,
                volno=True,
                od=None,
                do=None,
            )


def _ensure_owner_flow_user(salon) -> FlowUser:
    from rezervace.services.staff_auth import ensure_owner_flow_user

    user, _ = ensure_owner_flow_user(salon)
    return user


@transaction.atomic
def set_majitelka_pracuje(
    salon,
    *,
    ano: bool,
    jmeno: str | None = None,
    zamestnanec_id: int | None = None,
    skryt_pri_vypnuti: bool = True,
) -> dict:
    """
    Zapne/vypne pracovní personu majitelky.
    Při zapnutí: vytvoří nebo propojí Zamestnanec (role=zamestnanec), web+rozvrh.
    Při vypnutí: odpojí od FlowUser; volitelně skryje z webu (záznam zůstane).
    """
    flow_user = _ensure_owner_flow_user(salon)
    primary = flow_user.zamestnanec
    if primary.role != Zamestnanec.ROLE_MAJITEL:
        raise ValueError('FLOW účet není napojený na majitelku.')

    if not ano:
        pz = flow_user.pracovni_zamestnanec
        flow_user.pracovni_zamestnanec = None
        flow_user.save(update_fields=['pracovni_zamestnanec', 'upraveno'])
        if pz and skryt_pri_vypnuti:
            pz.zobrazit_na_webu = False
            pz.save(update_fields=['zobrazit_na_webu'])
        # Sessiony zpět na majitelku
        from flow.models import FlowSession

        FlowSession.objects.filter(user=flow_user).update(active_zamestnanec=primary)
        return majitelka_pracuje_payload(flow_user)

    # Zapnout
    zam = None
    if zamestnanec_id:
        zam = Zamestnanec.objects.filter(pk=zamestnanec_id, salon=salon).first()
        if not zam:
            raise ValueError('Pracovník nepatří k salonu.')
        if zam.role == Zamestnanec.ROLE_MAJITEL:
            raise ValueError('Vyberte běžný personál, ne účet majitelky.')
        if hasattr(zam, 'flow_ucet'):
            raise ValueError(
                'Tento pracovník už má vlastní FLOW login. '
                'Zvolte jiného, nebo nechte vytvořit novou personu.'
            )
    elif flow_user.pracovni_zamestnanec_id:
        zam = flow_user.pracovni_zamestnanec
    else:
        name = (jmeno or '').strip() or f'{primary.jmeno}'
        login = f'work.{flow_user.id}.{salon.id}@flow.local'
        zam = Zamestnanec.objects.create(
            salon=salon,
            jmeno=name[:120],
            role=Zamestnanec.ROLE_ZAMESTNANEC,
            prihlasovaci_jmeno=login[:100],
            aktivni=True,
            zobrazit_na_webu=True,
            specializace=primary.specializace or '',
        )

    zam.aktivni = True
    zam.zobrazit_na_webu = True
    if jmeno and jmeno.strip():
        zam.jmeno = jmeno.strip()[:120]
    zam.save()
    _default_rozvrh(zam)

    flow_user.pracovni_zamestnanec = zam
    flow_user.save(update_fields=['pracovni_zamestnanec', 'upraveno'])
    return majitelka_pracuje_payload(flow_user)
