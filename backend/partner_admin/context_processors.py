def nav_souhrn(request):
    """Počty do sidebaru jen na stránkách partner-admin, bez fiktivních notifikací."""
    path = getattr(request, 'path', '') or ''
    if not path.startswith('/partner-admin/'):
        return {}
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated or not user.is_superuser:
        return {}

    from django.utils import timezone

    from .models import PartnerNastaveni, TechnickaChyba

    dnes = timezone.localdate()
    po_splatnosti = PartnerNastaveni.objects.filter(dalsi_splatnost__lt=dnes).count()
    chyby = TechnickaChyba.objects.filter(vyreseno=False).count()
    return {
        'nav_po_splatnosti': po_splatnosti,
        'nav_chyby': chyby,
        'nav_pozornost': po_splatnosti + chyby,
    }
