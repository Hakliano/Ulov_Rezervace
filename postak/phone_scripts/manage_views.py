from django.contrib import messages
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from jadro.views import login_required_view, superuser_required

from phone_scripts.constants import VersionStatus
from phone_scripts.forms import ImportJsonForm, NewScriptForm, PublishConfirmForm
from phone_scripts.models import PhoneScript, PhoneScriptVersion
from phone_scripts.services.validate_snapshot import validate_snapshot_payload
from phone_scripts.services.versions import (
    VersionServiceError,
    create_script_with_draft,
    deactivate_script,
    import_new_draft_version,
    parse_uploaded_json,
    publish_version,
)


@login_required_view
@superuser_required
def sprava_seznam(request):
    scripts = PhoneScript.objects.prefetch_related('versions', 'current_version').order_by(
        'product', 'name'
    )
    rows = []
    for script in scripts:
        versions = script.versions.all()
        current = script.current_version
        rows.append(
            {
                'script': script,
                'version_count': versions.count(),
                'current_number': current.version_number if current else '—',
                'current_status': current.status_label if current else '—',
            }
        )
    return render(request, 'phone_scripts/sprava_seznam.html', {'rows': rows})


@login_required_view
@superuser_required
def sprava_verze(request, slug):
    script = get_object_or_404(PhoneScript, slug=slug)
    versions = script.versions.select_related('created_by').order_by('-version_number')
    return render(
        request,
        'phone_scripts/sprava_verze.html',
        {'script': script, 'versions': versions},
    )


@login_required_view
@superuser_required
@require_http_methods(['GET', 'POST'])
def sprava_novy(request):
    if request.method == 'POST':
        form = NewScriptForm(request.POST)
        if form.is_valid():
            from urllib.parse import urlencode

            query = urlencode(
                {
                    'name': form.cleaned_data['name'],
                    'slug': form.cleaned_data['slug'],
                    'product': form.cleaned_data['product'],
                }
            )
            return redirect(f"{reverse('telefonni_klikacka_sprava_import')}?{query}")
    else:
        form = NewScriptForm()
    return render(request, 'phone_scripts/sprava_novy.html', {'form': form})


@login_required_view
@superuser_required
@require_http_methods(['GET', 'POST'])
def sprava_import(request, slug=None):
    script = None
    if slug:
        script = get_object_or_404(PhoneScript, slug=slug)

    initial = {}
    if script:
        initial = {'mode': ImportJsonForm.MODE_VERSION, 'existing_script': script.pk}
    elif request.GET.get('slug'):
        try:
            script = PhoneScript.objects.get(slug=request.GET['slug'])
            initial = {'mode': ImportJsonForm.MODE_NEW, 'slug_prefill': script.slug}
        except PhoneScript.DoesNotExist:
            initial = {'mode': ImportJsonForm.MODE_NEW}
            form_data = NewScriptForm(request.GET)
            if form_data.is_valid():
                initial['new_name'] = form_data.cleaned_data.get('name')
    else:
        initial = {'mode': ImportJsonForm.MODE_NEW}

    preview = None
    if request.method == 'POST':
        form = ImportJsonForm(request.POST, request.FILES, initial=initial)
        if form.is_valid():
            raw = request.FILES['json_file'].read()
            try:
                data = parse_uploaded_json(raw)
            except VersionServiceError as exc:
                messages.error(request, str(exc))
            else:
                validation = validate_snapshot_payload(data)
                if not validation.ok:
                    for err in validation.errors:
                        messages.error(request, err)
                    preview = {'validation': validation, 'data': None}
                else:
                    mode = form.cleaned_data['mode']
                    note = form.cleaned_data.get('note') or ''
                    meta = data.get('meta') or {}
                    try:
                        if mode == ImportJsonForm.MODE_NEW:
                            name = request.POST.get('new_name') or meta.get('name') or 'Nový scénář'
                            new_slug = request.POST.get('new_slug') or meta.get('slug')
                            if not new_slug:
                                messages.error(request, 'Zadejte slug nového scénáře.')
                            else:
                                product = request.POST.get('new_product') or meta.get('product')
                                create_script_with_draft(
                                    name=name,
                                    slug=new_slug,
                                    product=product,
                                    snapshot=data,
                                    user=request.user,
                                    note=note,
                                )
                                messages.success(
                                    request,
                                    f'Scénář {new_slug} importován jako koncept (nepublikováno).',
                                )
                                return redirect('telefonni_klikacka_sprava_verze', slug=new_slug)
                        else:
                            target = form.cleaned_data['existing_script']
                            ver = import_new_draft_version(
                                target, data, user=request.user, note=note
                            )
                            messages.success(
                                request,
                                f'Verze v{ver.version_number} uložena jako koncept.',
                            )
                            return redirect('telefonni_klikacka_sprava_verze', slug=target.slug)
                    except VersionServiceError as exc:
                        messages.error(request, str(exc))
        else:
            for err in form.errors.values():
                messages.error(request, ' '.join(err))
    else:
        form = ImportJsonForm(initial=initial)

    new_script_defaults = {
        'name': request.GET.get('name', '') or (script.name if script else ''),
        'slug': slug or request.GET.get('slug', ''),
        'product': request.GET.get('product', script.product if script else 'modernik'),
    }

    return render(
        request,
        'phone_scripts/sprava_import.html',
        {
            'form': form,
            'script': script,
            'preview': preview,
            'new_script_defaults': new_script_defaults,
        },
    )


@login_required_view
@superuser_required
@require_GET
def sprava_export(request, version_id):
    version = get_object_or_404(PhoneScriptVersion.objects.select_related('script'), pk=version_id)
    import json

    payload = json.dumps(version.snapshot, ensure_ascii=False, indent=2)
    filename = f'{version.script.slug}-v{version.version_number}.json'
    response = HttpResponse(payload, content_type='application/json; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required_view
@superuser_required
@require_http_methods(['GET', 'POST'])
def sprava_publikovat(request, version_id):
    version = get_object_or_404(
        PhoneScriptVersion.objects.select_related('script'),
        pk=version_id,
    )
    validation = validate_snapshot_payload(version.snapshot)
    if request.method == 'POST':
        form = PublishConfirmForm(request.POST)
        if form.is_valid():
            if not validation.ok:
                messages.error(request, 'Verze neprošla validací.')
            else:
                publish_version(version)
                messages.success(
                    request,
                    f'Publikováno: {version.script.name} v{version.version_number}.',
                )
                return redirect('telefonni_klikacka_sprava_verze', slug=version.script.slug)
    else:
        form = PublishConfirmForm()
    return render(
        request,
        'phone_scripts/sprava_publikovat.html',
        {
            'version': version,
            'form': form,
            'validation': validation,
        },
    )


@login_required_view
@superuser_required
@require_POST
def sprava_deaktivovat(request, slug):
    script = get_object_or_404(PhoneScript, slug=slug)
    deactivate_script(script)
    messages.success(request, f'Scénář {script.name} deaktivován.')
    return redirect('telefonni_klikacka_sprava_seznam')


@login_required_view
@superuser_required
def sprava_testovat(request, version_id):
    version = get_object_or_404(PhoneScriptVersion, pk=version_id)
    if version.status not in (VersionStatus.DRAFT, VersionStatus.ARCHIVED, VersionStatus.PUBLISHED):
        return HttpResponseForbidden('Verzi nelze testovat.')
    url = reverse('telefonni_klikacka') + f'?test_version={version.pk}'
    return redirect(url)
