"""Unikátní e-mail loginy majitelů (napříč salony)."""

from __future__ import annotations

from rezervace.models import Zamestnanec


def _je_email(hodnota: str) -> bool:
    v = (hodnota or '').strip()
    return '@' in v and '.' in v.split('@')[-1]


def normalizuj_email(hodnota: str) -> str:
    return (hodnota or '').strip().lower()


def _email_je_volny(email: str, exclude_staff_id: int | None = None) -> bool:
    from flow.models import FlowUser

    email_n = normalizuj_email(email)
    qs_staff = Zamestnanec.objects.filter(prihlasovaci_jmeno__iexact=email_n)
    qs_flow = FlowUser.objects.filter(email__iexact=email_n)
    if exclude_staff_id:
        qs_staff = qs_staff.exclude(pk=exclude_staff_id)
        qs_flow = qs_flow.exclude(zamestnanec_id=exclude_staff_id)
    return not qs_staff.exists() and not qs_flow.exists()


def navrhni_unikatni_owner_email(staff: Zamestnanec, reserved: set[str] | None = None) -> str:
    """
    Preferuje platný ASCII salon.email, jinak majitel.salon{id}@ulov.local,
    případně s číselnou příponou při kolizi.
    """
    reserved = reserved if reserved is not None else set()
    salon = staff.salon
    candidates = []
    salon_email = normalizuj_email(getattr(salon, 'email', '') or '')
    # Django EmailField / SMTP: držet se ASCII adres
    if _je_email(salon_email) and salon_email.isascii():
        candidates.append(salon_email)
    candidates.append(f'majitel.salon{salon.pk}@ulov.local')
    for i in range(2, 50):
        candidates.append(f'majitel.salon{salon.pk}.{i}@ulov.local')

    for cand in candidates:
        if cand in reserved:
            continue
        if not _email_je_volny(cand, exclude_staff_id=staff.pk):
            continue
        return cand
    raise ValueError(f'Nepodařilo se navrhnout unikátní e-mail pro salon {salon.pk}')


def plan_owner_email_fixes() -> list[dict]:
    """
    Najde majitele, kteří:
    - nemají login jako e-mail, nebo
    - mají stejný login jako jiný majitel / FlowUser,
    a navrhne unikátní e-mail.
    """
    from flow.models import FlowUser

    owners = list(
        Zamestnanec.objects.filter(role=Zamestnanec.ROLE_MAJITEL)
        .select_related('salon')
        .order_by('salon_id', 'id')
    )
    # kolize: stejný login u více majitelů
    counts: dict[str, int] = {}
    for o in owners:
        key = normalizuj_email(o.prihlasovaci_jmeno)
        if key:
            counts[key] = counts.get(key, 0) + 1

    reserved: set[str] = set()
    # rezervuj už platné unikátní e-maily majitelů, které necháme
    for o in owners:
        login = normalizuj_email(o.prihlasovaci_jmeno)
        if _je_email(login) and counts.get(login, 0) == 1:
            # i FlowUser na jiném účtu?
            conflict = FlowUser.objects.filter(email__iexact=login).exclude(zamestnanec_id=o.id).exists()
            if not conflict:
                reserved.add(login)

    plan: list[dict] = []
    for o in owners:
        old = normalizuj_email(o.prihlasovaci_jmeno)
        needs = False
        reason = ''
        if not _je_email(old):
            needs = True
            reason = 'není e-mail'
        elif counts.get(old, 0) > 1:
            needs = True
            reason = 'duplicitní login'
        elif FlowUser.objects.filter(email__iexact=old).exclude(zamestnanec_id=o.id).exists():
            needs = True
            reason = 'kolize s FlowUser'
        elif old in reserved and any(r['staff_id'] != o.id and r.get('new') == old for r in plan):
            needs = True
            reason = 'kolize v plánu'

        if not needs:
            reserved.add(old)
            continue

        new = navrhni_unikatni_owner_email(o, reserved=reserved)
        reserved.add(new)
        plan.append(
            {
                'staff_id': o.id,
                'salon_id': o.salon_id,
                'salon_name': o.salon.name,
                'old': o.prihlasovaci_jmeno or '',
                'new': new,
                'reason': reason,
            }
        )
    return plan


def apply_owner_email_fixes(plan: list[dict] | None = None) -> int:
    """Aplikuje plán (nebo sestaví nový) — sync Zamestnanec + FlowUser."""
    from flow.models import FlowUser

    if plan is None:
        plan = plan_owner_email_fixes()
    changed = 0
    for row in plan:
        staff = Zamestnanec.objects.select_related('salon').get(pk=row['staff_id'])
        new = normalizuj_email(row['new'])
        if staff.prihlasovaci_jmeno != new:
            staff.prihlasovaci_jmeno = new
            staff.save(update_fields=['prihlasovaci_jmeno'])
            changed += 1
        try:
            flow = staff.flow_ucet
        except FlowUser.DoesNotExist:
            flow = None
        if flow is not None and flow.email != new:
            flow.email = new
            flow.save(update_fields=['email', 'upraveno'])
    return changed
