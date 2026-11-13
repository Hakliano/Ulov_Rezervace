from __future__ import annotations

import json

from django.db import transaction
from django.utils import timezone

from phone_scripts.constants import VersionStatus
from phone_scripts.models import PhoneScript, PhoneScriptVersion
from phone_scripts.services.validate_snapshot import (
    SnapshotValidationResult,
    normalize_snapshot_meta,
    validate_snapshot_payload,
)


class VersionServiceError(Exception):
    pass


def next_version_number(script: PhoneScript) -> int:
    last = script.versions.order_by('-version_number').values_list('version_number', flat=True).first()
    return (last or 0) + 1


@transaction.atomic
def create_script_with_draft(
    *,
    name: str,
    slug: str,
    product: str,
    snapshot: dict,
    user,
    note: str = '',
) -> tuple[PhoneScript, PhoneScriptVersion]:
    validation = validate_snapshot_payload(snapshot)
    if not validation.ok:
        raise VersionServiceError('\n'.join(validation.errors))
    if PhoneScript.objects.filter(slug=slug).exists():
        raise VersionServiceError(f'Scénář se slugem {slug} již existuje.')
    script = PhoneScript.objects.create(
        name=name,
        slug=slug,
        product=product,
        is_active=False,
    )
    version = _create_draft_version(script, snapshot, user=user, note=note, version_number=1)
    return script, version


@transaction.atomic
def import_new_draft_version(
    script: PhoneScript,
    snapshot: dict,
    *,
    user,
    note: str = '',
) -> PhoneScriptVersion:
    validation = validate_snapshot_payload(snapshot)
    if not validation.ok:
        raise VersionServiceError('\n'.join(validation.errors))
    num = next_version_number(script)
    return _create_draft_version(script, snapshot, user=user, note=note, version_number=num)


def _create_draft_version(
    script: PhoneScript,
    snapshot: dict,
    *,
    user,
    note: str,
    version_number: int,
) -> PhoneScriptVersion:
    payload = normalize_snapshot_meta(
        snapshot,
        script_slug=script.slug,
        script_name=script.name,
        version_number=version_number,
    )
    return PhoneScriptVersion.objects.create(
        script=script,
        version_number=version_number,
        status=VersionStatus.DRAFT,
        is_current=False,
        snapshot=payload,
        note=note,
        created_by=user,
    )


@transaction.atomic
def publish_version(version: PhoneScriptVersion) -> SnapshotValidationResult:
    validation = validate_snapshot_payload(version.snapshot)
    if not validation.ok:
        return validation

    script = version.script
    now = timezone.now()

    PhoneScriptVersion.objects.filter(script=script, is_current=True).update(
        is_current=False,
        status=VersionStatus.ARCHIVED,
    )
    PhoneScriptVersion.objects.filter(script=script, status=VersionStatus.PUBLISHED).update(
        status=VersionStatus.ARCHIVED,
        is_current=False,
    )

    payload = normalize_snapshot_meta(
        version.snapshot,
        script_slug=script.slug,
        script_name=script.name,
        version_number=version.version_number,
    )
    version.snapshot = payload
    version.status = VersionStatus.PUBLISHED
    version.is_current = True
    version.published_at = now
    version.save(update_fields=['snapshot', 'status', 'is_current', 'published_at'])

    script.current_version = version
    script.version = version.version_number
    script.published_snapshot = payload
    script.published_at = now
    script.is_active = True
    script.save(
        update_fields=[
            'current_version',
            'version',
            'published_snapshot',
            'published_at',
            'is_active',
            'updated_at',
        ]
    )
    return validation


@transaction.atomic
def deactivate_script(script: PhoneScript) -> None:
    script.is_active = False
    script.save(update_fields=['is_active', 'updated_at'])


def parse_uploaded_json(raw: bytes) -> dict:
    try:
        text = raw.decode('utf-8-sig')
    except UnicodeDecodeError as exc:
        raise VersionServiceError('Soubor musí být v UTF-8.') from exc
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise VersionServiceError(f'Neplatný JSON: {exc}') from exc


def user_may_play_version(user, version: PhoneScriptVersion) -> bool:
    script = version.script
    if version.status == VersionStatus.DRAFT:
        return user.is_superuser
    if version.status == VersionStatus.ARCHIVED:
        return user.is_superuser
    if version.status == VersionStatus.PUBLISHED:
        if user.is_superuser:
            return True
        return script.is_active and version.is_current
    return False


def versions_visible_to_user(user, script: PhoneScript):
    qs = script.versions.all()
    if user.is_superuser:
        return qs
    return qs.filter(status=VersionStatus.PUBLISHED, is_current=True)
