from __future__ import annotations

from django.db import transaction
from django.db.models import Prefetch
from django.utils import timezone

from phone_scripts.constants import SpecialAction, branch_key
from phone_scripts.models import (
    AnswerOption,
    Objection,
    ObjectionResponse,
    OpeningGreeting,
    PhoneScript,
    ProductPriceRow,
    ScriptStep,
)
from phone_scripts.services.validate import validate_script


def build_snapshot(script: PhoneScript) -> dict:
    steps = {
        s.step_id: s
        for s in ScriptStep.objects.filter(script=script).select_related('topic_area')
    }
    steps_payload = {}
    for sid, step in steps.items():
        answers = []
        for ans in AnswerOption.objects.filter(step=step).order_by('sort_order', 'pk'):
            item = {
                'id': f'a{ans.pk}',
                'label': ans.label,
                'sortOrder': ans.sort_order,
            }
            if ans.special_action == SpecialAction.END_CALL:
                item['endCall'] = True
            elif ans.special_action == SpecialAction.JUMP_TOPIC and ans.jump_area:
                item['jumpAreaSlug'] = ans.jump_area.slug
            elif ans.target_step_id:
                item['targetStepId'] = ans.target_step.step_id
            answers.append(item)
        steps_payload[sid] = {
            'stepId': sid,
            'type': step.step_type,
            'say': step.say_text,
            'goal': step.goal_note,
            'areaSlug': step.topic_area.slug if step.topic_area_id else None,
            'answers': answers,
        }

    areas_payload = {}
    for area in script.areas.select_related('entry_step').order_by('sort_order', 'pk'):
        areas_payload[area.slug] = {
            'slug': area.slug,
            'name': area.name,
            'sortOrder': area.sort_order,
            'entryStepId': area.entry_step.step_id if area.entry_step_id else None,
        }

    branches_payload = {}
    for br in script.initial_branches.select_related('entry_step'):
        key = branch_key(br.web_status, br.sales_style)
        branches_payload[key] = br.entry_step.step_id

    openings = [
        {'id': f'o{o.pk}', 'name': o.name, 'text': o.text, 'sortOrder': o.sort_order}
        for o in OpeningGreeting.objects.filter(script=script).order_by('sort_order', 'pk')
    ]

    objections_payload = {}
    for obj in Objection.objects.filter(script=script).prefetch_related(
        Prefetch(
            'responses',
            queryset=ObjectionResponse.objects.select_related('target_step'),
        )
    ).order_by('sort_order', 'pk'):
        responses = []
        for resp in obj.responses.all():
            r = {
                'id': f'or{resp.pk}',
                'say': resp.say_text,
                'sortOrder': resp.sort_order,
                'hardReject': resp.hard_reject,
                'returnOnly': resp.return_only,
            }
            if resp.target_step_id:
                r['targetStepId'] = resp.target_step.step_id
            responses.append(r)
        objections_payload[obj.slug] = {
            'slug': obj.slug,
            'title': obj.title,
            'sortOrder': obj.sort_order,
            'rootStepId': obj.root_step.step_id if obj.root_step_id else None,
            'responses': responses,
        }

    pricing = [
        {
            'productName': row.product_name,
            'monthlyCzk': row.monthly_czk,
            'activationCzk': row.activation_czk,
            'description': row.description_short,
            'sortOrder': row.sort_order,
        }
        for row in ProductPriceRow.objects.filter(script=script).order_by('sort_order', 'pk')
    ]

    return {
        'meta': {
            'slug': script.slug,
            'name': script.name,
            'product': script.product,
            'version': script.version,
        },
        'initialBranches': branches_payload,
        'openings': openings,
        'areas': areas_payload,
        'steps': steps_payload,
        'objections': objections_payload,
        'pricing': pricing,
    }


@transaction.atomic
def publish_script(script: PhoneScript, *, user=None) -> tuple[bool, list[str]]:
    validation = validate_script(script)
    if not validation.ok:
        return False, validation.errors
    snapshot = build_snapshot(script)
    from phone_scripts.services.versions import import_new_draft_version, publish_version

    version = import_new_draft_version(script, snapshot, user=user, note='Publikace z ORM / admin')
    pub_validation = publish_version(version)
    return pub_validation.ok, validation.warnings + pub_validation.warnings
