# Generated manually for unique owner email logins

from django.db import migrations, models


def forwards_unique_owner_emails(apps, schema_editor):
    """Přepíše majitel/majitelka a duplicity na unikátní e-maily před constraint."""
    Zamestnanec = apps.get_model('rezervace', 'Zamestnanec')
    FlowUser = apps.get_model('flow', 'FlowUser')

    def is_email(v):
        v = (v or '').strip()
        return '@' in v and '.' in v.split('@')[-1]

    def norm(v):
        return (v or '').strip().lower()

    owners = list(
        Zamestnanec.objects.filter(role='majitel').select_related('salon').order_by('salon_id', 'id')
    )
    counts = {}
    for o in owners:
        key = norm(o.prihlasovaci_jmeno)
        if key:
            counts[key] = counts.get(key, 0) + 1

    reserved = set()
    for o in owners:
        login = norm(o.prihlasovaci_jmeno)
        if is_email(login) and counts.get(login, 0) == 1:
            if not FlowUser.objects.filter(email__iexact=login).exclude(zamestnanec_id=o.id).exists():
                reserved.add(login)

    def free(email, exclude_id):
        if email in reserved:
            return False
        if Zamestnanec.objects.filter(prihlasovaci_jmeno__iexact=email).exclude(pk=exclude_id).exists():
            return False
        if FlowUser.objects.filter(email__iexact=email).exclude(zamestnanec_id=exclude_id).exists():
            return False
        return True

    def suggest(o):
        cands = []
        se = norm(getattr(o.salon, 'email', '') or '')
        if is_email(se) and se.isascii():
            cands.append(se)
        cands.append(f'majitel.salon{o.salon_id}@ulov.local')
        for i in range(2, 50):
            cands.append(f'majitel.salon{o.salon_id}.{i}@ulov.local')
        for c in cands:
            if free(c, o.id):
                return c
        raise RuntimeError(f'No unique email for salon {o.salon_id}')

    for o in owners:
        old = norm(o.prihlasovaci_jmeno)
        needs = (
            not is_email(old)
            or counts.get(old, 0) > 1
            or FlowUser.objects.filter(email__iexact=old).exclude(zamestnanec_id=o.id).exists()
        )
        if not needs:
            reserved.add(old)
            continue
        new = suggest(o)
        reserved.add(new)
        if o.prihlasovaci_jmeno != new:
            o.prihlasovaci_jmeno = new
            o.save(update_fields=['prihlasovaci_jmeno'])
        flow = FlowUser.objects.filter(zamestnanec_id=o.id).first()
        if flow and flow.email != new:
            flow.email = new
            flow.save(update_fields=['email'])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('rezervace', '0031_zamestnanec_sluzba'),
        ('flow', '0002_flow_mail_odeslano'),
    ]

    operations = [
        migrations.AlterField(
            model_name='zamestnanec',
            name='prihlasovaci_jmeno',
            field=models.CharField(blank=True, max_length=254, verbose_name='přihlašovací e-mail / jméno'),
        ),
        migrations.RunPython(forwards_unique_owner_emails, noop_reverse),
        migrations.AddConstraint(
            model_name='zamestnanec',
            constraint=models.UniqueConstraint(
                condition=models.Q(('role', 'majitel')) & ~models.Q(('prihlasovaci_jmeno', '')),
                fields=('prihlasovaci_jmeno',),
                name='unique_owner_prihlasovaci_email',
            ),
        ),
    ]
