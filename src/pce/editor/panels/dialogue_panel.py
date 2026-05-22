from __future__ import annotations

import copy

from pce.editor.panels.action_list_panel import actions_from_json, action_to_json
from pce.editor.panels.action_list_panel import condition_from_json, condition_to_json
from pce.shared.models import DialogueChoice


def choice_label(index: int, choice: DialogueChoice) -> str:
    suffix = f" -> {choice.target}" if choice.target else ""
    gated = " [condition]" if choice.condition is not None else ""
    acts = f" [{len(choice.actions)} actions]" if choice.actions else ""
    return f"{index + 1}. {choice.text}{suffix}{gated}{acts}"


def merge_choice_from_fields(
    existing: DialogueChoice | None,
    *,
    text: str,
    target: str = "",
    condition_json: str = "",
    actions_json: str = "",
) -> DialogueChoice:
    choice = copy.deepcopy(existing) if existing is not None else DialogueChoice(text=text)
    choice.text = text
    choice.target = target or None
    if condition_json.strip():
        choice.condition = condition_from_json(condition_json)
    if actions_json.strip():
        choice.actions = actions_from_json(actions_json)
    return choice


def choice_condition_json(choice: DialogueChoice | None) -> str:
    return condition_to_json(choice.condition if choice is not None else None)


def choice_actions_json(choice: DialogueChoice | None) -> str:
    return action_to_json([] if choice is None else choice.actions)
