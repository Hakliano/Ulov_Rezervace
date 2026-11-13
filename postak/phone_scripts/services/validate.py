from __future__ import annotations

from dataclasses import dataclass, field

from django.db.models import Prefetch

from phone_scripts.constants import ALL_BRANCH_KEYS, SpecialAction, StepType, branch_key
from phone_scripts.models import (
    AnswerOption,
    InitialBranch,
    PhoneScript,
    ScriptStep,
)


@dataclass
class ValidationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def validate_script(script: PhoneScript) -> ValidationResult:
    result = ValidationResult(ok=True)
    step_ids = set(
        ScriptStep.objects.filter(script=script).values_list('step_id', flat=True)
    )
    if not step_ids:
        result.errors.append('Scénář nemá žádné kroky.')
        result.ok = False
        return result

    steps = (
        ScriptStep.objects.filter(script=script)
        .prefetch_related(
            Prefetch(
                'answers',
                queryset=AnswerOption.objects.select_related('target_step', 'jump_area'),
            )
        )
    )
    step_by_id = {s.step_id: s for s in steps}

    for step in steps:
        if step.step_type == StepType.QUESTION and not step.answers.exists():
            result.errors.append(f'Krok {step.step_id}: otázka bez odpovědí.')

    for step in steps:
        for ans in step.answers.all():
            if ans.special_action == SpecialAction.END_CALL:
                continue
            if ans.special_action == SpecialAction.JUMP_TOPIC:
                if not ans.jump_area_id:
                    result.errors.append(
                        f'Krok {step.step_id}, odpověď „{ans.label[:40]}“: chybí oblast pro přeskok.'
                    )
                continue
            if not ans.target_step_id:
                result.errors.append(
                    f'Krok {step.step_id}, odpověď „{ans.label[:40]}“: chybí cílový krok.'
                )
            elif ans.target_step.script_id != script.pk:
                result.errors.append(
                    f'Krok {step.step_id}: cíl vede do jiného scénáře ({ans.target_step.step_id}).'
                )

    branches = InitialBranch.objects.filter(script=script).select_related('entry_step')
    branch_keys = {branch_key(b.web_status, b.sales_style) for b in branches}
    for key in ALL_BRANCH_KEYS:
        if key not in branch_keys:
            result.errors.append(f'Chybí vstupní větev: {key}.')

    for branch in branches:
        if branch.entry_step.script_id != script.pk:
            result.errors.append(f'Větev {branch}: vstupní krok patří jinému scénáři.')
        if branch.entry_step.step_id not in step_by_id:
            result.errors.append(f'Větev {branch}: neplatný vstupní krok.')

    has_exit = any(s.step_type in (StepType.POLITE_EXIT, StepType.CLOSING) for s in steps)
    has_end_answer = AnswerOption.objects.filter(
        step__script=script, special_action=SpecialAction.END_CALL
    ).exists()
    if not has_exit and not has_end_answer:
        result.errors.append('Scénář nemá definované ukončení hovoru.')

    orphans = step_ids - _reachable_from_branches(script, step_by_id, branches)
    if orphans:
        result.warnings.append(
            f'Nedosažitelné kroky ({len(orphans)}): {", ".join(sorted(list(orphans))[:8])}'
            + ('…' if len(orphans) > 8 else '')
        )

    if result.errors:
        result.ok = False
    return result


def _reachable_from_branches(script, step_by_id, branches) -> set[str]:
    seen: set[str] = set()
    stack = [b.entry_step.step_id for b in branches]
    while stack:
        sid = stack.pop()
        if sid in seen or sid not in step_by_id:
            continue
        seen.add(sid)
        step = step_by_id[sid]
        for ans in step.answers.all():
            if ans.special_action == SpecialAction.END_CALL:
                continue
            if ans.special_action == SpecialAction.JUMP_TOPIC and ans.jump_area:
                entry = ans.jump_area.entry_step
                if entry and entry.step_id in step_by_id:
                    stack.append(entry.step_id)
                continue
            if ans.target_step_id:
                stack.append(ans.target_step.step_id)
    return seen
