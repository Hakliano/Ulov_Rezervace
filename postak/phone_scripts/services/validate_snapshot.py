from __future__ import annotations

from dataclasses import dataclass, field

from phone_scripts.constants import ALL_BRANCH_KEYS, StepType, branch_key


@dataclass
class SnapshotValidationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def validate_snapshot_payload(data: dict) -> SnapshotValidationResult:
    result = SnapshotValidationResult(ok=True)
    if not isinstance(data, dict):
        result.errors.append('Kořen souboru musí být JSON objekt.')
        result.ok = False
        return result

    meta = data.get('meta')
    if not meta or not meta.get('product'):
        result.errors.append('Chybí meta.product.')
    product = (meta or {}).get('product')
    if product and product not in ('modernik', 'hereyouare'):
        result.errors.append(f'Neplatný meta.product: {product}')

    steps = data.get('steps')
    if not steps or not isinstance(steps, dict):
        result.errors.append('Chybí nebo je prázdný objekt steps.')
        result.ok = False
        return result

    branches = data.get('initialBranches') or {}
    if not isinstance(branches, dict):
        result.errors.append('initialBranches musí být objekt.')
    for key in ALL_BRANCH_KEYS:
        if key not in branches:
            result.errors.append(f'Chybí vstupní větev: {key}.')
        else:
            entry = branches[key]
            if entry not in steps:
                result.errors.append(f'Větev {key}: neznámý vstupní krok {entry}.')

    areas = data.get('areas') or {}
    area_slugs = set()
    if isinstance(areas, dict):
        area_slugs = set(areas.keys())

    for sid, step in steps.items():
        if not isinstance(step, dict):
            result.errors.append(f'Krok {sid}: neplatná struktura.')
            continue
        step_type = step.get('type') or StepType.QUESTION
        answers = step.get('answers') or []
        if step_type == StepType.QUESTION and not answers:
            result.errors.append(f'Krok {sid}: otázka bez odpovědí.')
        area_slug = step.get('areaSlug')
        if area_slug and area_slug not in area_slugs:
            result.warnings.append(f'Krok {sid}: oblast {area_slug} není v areas.')
        for ans in answers:
            if not isinstance(ans, dict):
                continue
            if ans.get('endCall'):
                continue
            if ans.get('jumpAreaSlug'):
                if ans['jumpAreaSlug'] not in area_slugs:
                    result.errors.append(
                        f'Krok {sid}, odpověď „{(ans.get("label") or "")[:30]}“: neznámá oblast.'
                    )
                continue
            tid = ans.get('targetStepId')
            if not tid:
                result.errors.append(
                    f'Krok {sid}, odpověď „{(ans.get("label") or "")[:30]}“: chybí cílový krok.'
                )
            elif tid not in steps:
                result.errors.append(f'Krok {sid}: neznámý cíl {tid}.')

    has_exit = any(
        (s.get('type') in (StepType.POLITE_EXIT, StepType.CLOSING))
        for s in steps.values()
        if isinstance(s, dict)
    )
    has_end = any(
        ans.get('endCall')
        for s in steps.values()
        if isinstance(s, dict)
        for ans in (s.get('answers') or [])
        if isinstance(ans, dict)
    )
    if not has_exit and not has_end:
        result.errors.append('Scénář nemá definované ukončení hovoru.')

    reachable = _reachable_step_ids(branches, steps)
    orphans = set(steps.keys()) - reachable
    if orphans:
        result.warnings.append(
            f'Nedosažitelné kroky ({len(orphans)}): '
            + ', '.join(sorted(orphans)[:8])
            + ('…' if len(orphans) > 8 else '')
        )

    objections = data.get('objections') or {}
    if isinstance(objections, dict):
        for slug, obj in objections.items():
            rid = obj.get('rootStepId') if isinstance(obj, dict) else None
            if rid and rid not in steps:
                result.errors.append(f'Námitka {slug}: neznámý rootStepId {rid}.')
            for resp in (obj.get('responses') or []) if isinstance(obj, dict) else []:
                tid = resp.get('targetStepId')
                if tid and tid not in steps:
                    result.errors.append(f'Námitka {slug}: neznámý targetStepId {tid}.')

    if result.errors:
        result.ok = False
    return result


def _reachable_step_ids(branches: dict, steps: dict) -> set[str]:
    seen: set[str] = set()
    stack = [branches[k] for k in ALL_BRANCH_KEYS if k in branches]
    while stack:
        sid = stack.pop()
        if sid in seen or sid not in steps:
            continue
        seen.add(sid)
        step = steps[sid]
        if not isinstance(step, dict):
            continue
        for ans in step.get('answers') or []:
            if not isinstance(ans, dict):
                continue
            if ans.get('endCall'):
                continue
            if ans.get('jumpAreaSlug'):
                areas = {}
                continue
            tid = ans.get('targetStepId')
            if tid:
                stack.append(tid)
    return seen


def normalize_snapshot_meta(data: dict, *, script_slug: str, script_name: str, version_number: int) -> dict:
    """Zajistí konzistentní meta ve snapshotu uložené verze."""
    payload = dict(data)
    meta = dict(payload.get('meta') or {})
    meta['slug'] = script_slug
    meta['name'] = script_name
    meta['version'] = version_number
    payload['meta'] = meta
    return payload
