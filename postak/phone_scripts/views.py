from django.core.exceptions import PermissionDenied
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_GET

from jadro.views import login_required_view

from phone_scripts.constants import Product, VersionStatus
from phone_scripts.models import PhoneScript, PhoneScriptVersion
from phone_scripts.services.versions import user_may_play_version


def _versions_for_prep(user, script):
    if user.is_superuser:
        return script.versions.order_by('-version_number')
    return script.versions.filter(status=VersionStatus.PUBLISHED, is_current=True)


def _build_catalog(user):
    scenarios = []
    for script in PhoneScript.objects.prefetch_related('versions', 'current_version').order_by(
        'product', 'name'
    ):
        if not user.is_superuser and not script.is_active:
            continue
        version_rows = []
        for ver in _versions_for_prep(user, script):
            version_rows.append(
                {
                    'id': ver.pk,
                    'number': ver.version_number,
                    'status': ver.status,
                    'statusLabel': ver.status_label,
                    'isCurrent': ver.is_current,
                    'isDefault': ver.is_current and ver.status == VersionStatus.PUBLISHED,
                }
            )
        if not version_rows:
            continue
        current = script.current_version
        scenarios.append(
            {
                'id': script.pk,
                'slug': script.slug,
                'name': script.name,
                'product': script.product,
                'productLabel': Product(script.product).label,
                'isActive': script.is_active,
                'currentVersionId': current.pk if current else None,
                'versions': version_rows,
            }
        )
    return scenarios


@login_required_view
def priprava(request):
    test_version_id = request.GET.get('test_version')
    default_name = (request.user.get_full_name() or '').strip() or request.user.username
    preselect_version = None
    if test_version_id:
        if not request.user.is_superuser:
            raise PermissionDenied
        preselect_version = get_object_or_404(PhoneScriptVersion, pk=test_version_id)

    phone_clicker_config = {
        'scenarios': _build_catalog(request.user),
        'snapshotUrlTemplate': reverse(
            'telefonni_klikacka_snapshot_version',
            kwargs={'version_id': 0},
        ).replace('/0/', '/__VERSION_ID__/'),
        'defaultAgentName': default_name,
        'isSuperuser': request.user.is_superuser,
        'preselectVersionId': preselect_version.pk if preselect_version else None,
        'preselectScriptId': preselect_version.script_id if preselect_version else None,
        'manageUrl': reverse('telefonni_klikacka_sprava_seznam') if request.user.is_superuser else None,
    }
    return render(
        request,
        'phone_scripts/priprava.html',
        {
            'phone_clicker_config': phone_clicker_config,
            'default_agent_name': default_name,
            'catalog_empty': not phone_clicker_config['scenarios'],
        },
    )


@login_required_view
@require_GET
def snapshot_api_version(request, version_id):
    version = get_object_or_404(
        PhoneScriptVersion.objects.select_related('script'),
        pk=version_id,
    )
    if not user_may_play_version(request.user, version):
        raise PermissionDenied
    if not version.snapshot:
        raise Http404('Snapshot chybí.')
    response = JsonResponse(version.snapshot)
    response['Cache-Control'] = 'private, max-age=0, must-revalidate'
    response['X-Script-Version'] = str(version.version_number)
    response['X-Script-Slug'] = version.script.slug
    return response


@login_required_view
@require_GET
def snapshot_api(request, slug):
    """Zpětná kompatibilita: aktuální publikovaná verze scénáře podle slugu."""
    script = get_object_or_404(PhoneScript, slug=slug, is_active=True)
    version = script.current_version
    if not version or not version.snapshot:
        if script.published_snapshot:
            response = JsonResponse(script.published_snapshot)
            response['Cache-Control'] = 'private, max-age=0, must-revalidate'
            response['X-Script-Version'] = str(script.version)
            return response
        raise Http404('Scénář není publikován.')
    if not user_may_play_version(request.user, version):
        raise PermissionDenied
    response = JsonResponse(version.snapshot)
    response['Cache-Control'] = 'private, max-age=0, must-revalidate'
    response['X-Script-Version'] = str(version.version_number)
    return response
