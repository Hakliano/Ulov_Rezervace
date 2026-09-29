from .permissions import READ, muze_do_panelu, muze_videt, priznaky, role_label, zobrazovane_jmeno
from .pristupy import prostredi_navesti


def _prostredi_context():
    label = prostredi_navesti()
    return {
        'pa_prostredi': label,
        'pa_je_staging': label == 'Staging',
        'pa_je_lokal': label == 'Lokál',
    }


def nav_souhrn(request):
    """Počty do sidebaru jen na stránkách partner-admin, bez fiktivních notifikací."""
    ctx = _prostredi_context()
    path = getattr(request, 'path', '') or ''
    if not path.startswith('/partner-admin/'):
        return ctx
    user = getattr(request, 'user', None)
    if not muze_do_panelu(user):
        return ctx

    from django.utils import timezone

    from .models import PartnerNastaveni, TechnickaChyba
    from .permissions import WRITE

    dnes = timezone.localdate()
    po_splatnosti = 0
    chyby = 0
    if muze_videt(user, 'platby'):
        po_splatnosti = PartnerNastaveni.objects.filter(dalsi_splatnost__lt=dnes).count()
    if muze_videt(user, 'chyby'):
        chyby = TechnickaChyba.objects.filter(vyreseno=False).count()
    ctx.update({
        'nav_po_splatnosti': po_splatnosti,
        'nav_chyby': chyby,
        'nav_pozornost': po_splatnosti + chyby,
        'pa_role_label': role_label(user),
        'pa_display_name': zobrazovane_jmeno(user),
        'pa_can_see': priznaky(user, READ),
        'pa_can_write': priznaky(user, WRITE),
        'pa_is_superuser': user.is_superuser,
    })
    return ctx
