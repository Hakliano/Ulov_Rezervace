from __future__ import annotations

import json
from typing import Any

from django.db import transaction

from phone_scripts.constants import Product, SalesStyle, StepType, WebStatus
from phone_scripts.models import (
    AnswerOption,
    InitialBranch,
    Objection,
    ObjectionResponse,
    OpeningGreeting,
    PhoneScript,
    ProductPriceRow,
    ScriptStep,
    ScriptTopicArea,
)
from phone_scripts.services.snapshot import build_snapshot


def export_script_to_dict(script: PhoneScript) -> dict:
    return build_snapshot(script)


def export_script_json(script: PhoneScript, indent: int = 2) -> str:
    return json.dumps(export_script_to_dict(script), ensure_ascii=False, indent=indent)


class ImportError(Exception):
    pass


def _require(data: dict, key: str):
    if key not in data:
        raise ImportError(f'Chybí povinné pole: {key}')
    return data[key]


@transaction.atomic
def import_script_from_dict(data: dict, *, slug: str | None = None, replace: bool = False) -> PhoneScript:
    meta = data.get('meta') or {}
    script_slug = slug or meta.get('slug')
    if not script_slug:
        raise ImportError('Chybí slug scénáře.')

    if PhoneScript.objects.filter(slug=script_slug).exists():
        if not replace:
            raise ImportError(f'Scénář {script_slug} již existuje (použijte replace).')
        script = PhoneScript.objects.get(slug=script_slug)
        script.initial_branches.all().delete()
        script.objections.all().delete()
        script.openings.all().delete()
        script.pricing.all().delete()
        ScriptTopicArea.objects.filter(script=script).update(entry_step=None)
        script.areas.all().delete()
        script.steps.all().delete()
    else:
        product = meta.get('product') or Product.MODERNIK
        if product not in Product.values:
            raise ImportError(f'Neplatný produkt: {product}')
        script = PhoneScript.objects.create(
            slug=script_slug,
            name=meta.get('name') or script_slug,
            product=product,
            is_active=False,
            version=0,
        )

    areas_data = data.get('areas') or {}
    area_objs: dict[str, ScriptTopicArea] = {}
    if isinstance(areas_data, dict):
        for slug_key, area in areas_data.items():
            area_objs[slug_key] = ScriptTopicArea.objects.create(
                script=script,
                slug=area.get('slug') or slug_key,
                name=area.get('name') or slug_key,
                sort_order=area.get('sortOrder', 0),
            )
    elif isinstance(areas_data, list):
        for area in areas_data:
            slug_key = area['slug']
            area_objs[slug_key] = ScriptTopicArea.objects.create(
                script=script,
                slug=slug_key,
                name=area['name'],
                sort_order=area.get('sortOrder', 0),
            )

    steps_data = _require(data, 'steps')
    step_objs: dict[str, ScriptStep] = {}
    for sid, step in steps_data.items():
        area_slug = step.get('areaSlug')
        area = area_objs.get(area_slug) if area_slug else None
        step_type = step.get('type') or StepType.QUESTION
        if step_type not in StepType.values:
            step_type = StepType.QUESTION
        step_objs[sid] = ScriptStep.objects.create(
            script=script,
            step_id=sid,
            topic_area=area,
            step_type=step_type,
            say_text=step.get('say') or '',
            goal_note=step.get('goal') or '',
        )

    for slug_key, area in area_objs.items():
        entry_id = None
        raw_area = areas_data.get(slug_key) if isinstance(areas_data, dict) else None
        if raw_area:
            entry_id = raw_area.get('entryStepId')
        if not entry_id:
            for sid, step in steps_data.items():
                if step.get('areaSlug') == slug_key:
                    entry_id = sid
                    break
        if entry_id and entry_id in step_objs:
            area.entry_step = step_objs[entry_id]
            area.save(update_fields=['entry_step'])

    for sid, step in steps_data.items():
        step_model = step_objs[sid]
        for ans in step.get('answers') or []:
            target = None
            jump_area = None
            special = ''
            if ans.get('endCall'):
                special = 'end_call'
            elif ans.get('jumpAreaSlug'):
                special = 'jump_topic'
                jump_area = area_objs.get(ans['jumpAreaSlug'])
            else:
                tid = ans.get('targetStepId')
                if tid:
                    if tid not in step_objs:
                        raise ImportError(f'Krok {sid}: neznámý cíl {tid}')
                    target = step_objs[tid]
            AnswerOption.objects.create(
                step=step_model,
                label=ans.get('label') or '—',
                sort_order=ans.get('sortOrder', 0),
                target_step=target,
                special_action=special,
                jump_area=jump_area,
            )

    branches = data.get('initialBranches') or {}
    for key, entry_id in branches.items():
        if '_' not in key:
            raise ImportError(f'Neplatný klíč větve: {key}')
        web_status, style = key.rsplit('_', 1)
        if web_status not in WebStatus.values:
            raise ImportError(f'Neplatný stav webu ve větvi: {key}')
        if style not in SalesStyle.values:
            raise ImportError(f'Neplatný styl ve větvi: {key}')
        if entry_id not in step_objs:
            raise ImportError(f'Větev {key}: neznámý vstupní krok {entry_id}')
        InitialBranch.objects.create(
            script=script,
            web_status=web_status,
            sales_style=style,
            entry_step=step_objs[entry_id],
        )

    for opening in data.get('openings') or []:
        OpeningGreeting.objects.create(
            script=script,
            name=opening.get('name') or 'Oslovení',
            text=opening.get('text') or '',
            sort_order=opening.get('sortOrder', 0),
        )

    objections = data.get('objections') or {}
    items = objections.values() if isinstance(objections, dict) else objections
    for obj in items:
        root = None
        rid = obj.get('rootStepId')
        if rid:
            if rid not in step_objs:
                raise ImportError(f'Námitka {obj.get("slug")}: neznámý root {rid}')
            root = step_objs[rid]
        objection = Objection.objects.create(
            script=script,
            slug=obj['slug'],
            title=obj.get('title') or obj['slug'],
            sort_order=obj.get('sortOrder', 0),
            root_step=root,
        )
        for resp in obj.get('responses') or []:
            target = None
            tid = resp.get('targetStepId')
            if tid:
                if tid not in step_objs:
                    raise ImportError(f'Námitka {obj.get("slug")}: neznámý cíl {tid}')
                target = step_objs[tid]
            ObjectionResponse.objects.create(
                objection=objection,
                say_text=resp.get('say') or '',
                sort_order=resp.get('sortOrder', 0),
                target_step=target,
                hard_reject=bool(resp.get('hardReject')),
                return_only=bool(resp.get('returnOnly', True)),
            )

    for row in data.get('pricing') or []:
        ProductPriceRow.objects.create(
            script=script,
            product_name=row.get('productName') or row.get('name') or 'Produkt',
            monthly_czk=int(row.get('monthlyCzk') or row.get('monthly') or 0),
            activation_czk=int(row.get('activationCzk') or row.get('activation') or 0),
            description_short=row.get('description') or row.get('descriptionShort') or '',
            sort_order=row.get('sortOrder', 0),
        )

    if meta.get('name'):
        script.name = meta['name']
        script.save(update_fields=['name', 'updated_at'])
    return script


def import_script_json(raw: str, **kwargs) -> PhoneScript:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ImportError(f'Neplatný JSON: {exc}') from exc
    return import_script_from_dict(data, **kwargs)
