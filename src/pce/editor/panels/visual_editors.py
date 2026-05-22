from __future__ import annotations

import copy
from typing import Any

from pce.editor.panels.action_list_panel import ACTION_TYPES, parse_action_value
from pce.shared.models import Action, Condition


CONDITION_TYPES = ["always", "variable", "has_item", "object_enabled", "not"]
CONDITION_OPERATORS = ["==", "!=", ">", ">=", "<", "<="]


def merge_condition_from_fields(
    existing: Condition | None,
    *,
    condition_type: str,
    variable: str = "",
    operator: str = "==",
    value: str = "",
    item: str = "",
    object_id: str = "",
    nested_condition: Condition | None = None,
) -> Condition | None:
    if not condition_type or condition_type == "always":
        return None
    if condition_type not in CONDITION_TYPES:
        raise ValueError(f"Unknown condition type: {condition_type}")

    condition = copy.deepcopy(existing) if existing is not None else Condition(type=condition_type)
    if condition.type != condition_type:
        condition = Condition(type=condition_type)

    if condition_type == "variable":
        condition.variable = variable or None
        condition.operator = operator or "=="
        condition.value = parse_action_value(value)
    elif condition_type == "has_item":
        condition.item = item or None
    elif condition_type == "object_enabled":
        condition.object_id = object_id or None
    elif condition_type == "not":
        condition.condition = copy.deepcopy(nested_condition) if nested_condition is not None else condition.condition
        if condition.condition is None:
            condition.condition = Condition(type="always")
    return condition


def condition_to_fields(condition: Condition | None) -> dict[str, Any]:
    if condition is None:
        return {
            "type": "always",
            "variable": "",
            "operator": "==",
            "value": "true",
            "item": "",
            "object_id": "",
            "nested_condition": None,
        }
    return {
        "type": condition.type,
        "variable": condition.variable or "",
        "operator": condition.operator or "==",
        "value": "" if condition.value is None else str(condition.value),
        "item": condition.item or "",
        "object_id": condition.object_id or "",
        "nested_condition": copy.deepcopy(condition.condition),
    }


def merge_action_from_visual_fields(
    existing: Action | None,
    *,
    action_type: str,
    speaker: str = "",
    text: str = "",
    npc: str = "",
    node: str = "",
    path: list[tuple[int, int]] | None = None,
    scene: str = "",
    spawn: str = "",
    item: str = "",
    object_id: str = "",
    variable: str = "",
    value: str = "",
    enabled: bool = False,
    actions: list[Action] | None = None,
    condition: Condition | None = None,
    if_actions: list[Action] | None = None,
    else_actions: list[Action] | None = None,
) -> Action:
    if action_type not in ACTION_TYPES:
        raise ValueError(f"Unknown action type: {action_type}")

    action = copy.deepcopy(existing) if existing is not None else Action(type=action_type)
    if action.type != action_type:
        action = Action(type=action_type)

    if action_type == "say":
        action.speaker = speaker or "Player"
        action.text = text
    elif action_type == "dialogue":
        action.npc = npc or action.npc
        action.node = node or None
    elif action_type == "move_player":
        action.path = list(path or [])
    elif action_type == "change_scene":
        action.scene = scene or None
        action.spawn = spawn or None
    elif action_type == "sequence":
        if actions is not None:
            action.actions = copy.deepcopy(actions)
    elif action_type == "set_variable":
        action.variable = variable or None
        action.value = parse_action_value(value)
    elif action_type in {"give_item", "remove_item"}:
        action.item = item or None
    elif action_type == "set_object_enabled":
        action.object_id = object_id or None
        action.enabled = enabled
    elif action_type == "conditional":
        action.condition = copy.deepcopy(condition) if condition is not None else action.condition
        if action.condition is None:
            action.condition = Condition()
        if if_actions is not None:
            action.if_actions = copy.deepcopy(if_actions)
        if else_actions is not None:
            action.else_actions = copy.deepcopy(else_actions)
    return action


def action_list_labels(actions: list[Action]) -> list[str]:
    return [f"{index + 1}. {action_label(action)}" for index, action in enumerate(actions)]


def action_label(action: Action) -> str:
    if action.type == "say":
        return f"say: {action.text or ''}".strip()
    if action.type == "dialogue":
        suffix = f"@{action.node}" if action.node else ""
        return f"dialogue {action.npc or ''}{suffix}".strip()
    if action.type == "change_scene":
        return f"change_scene: {action.scene or ''}"
    if action.type == "give_item":
        return f"give_item: {action.item or ''}"
    if action.type == "remove_item":
        return f"remove_item: {action.item or ''}"
    if action.type == "set_variable":
        return f"set_variable: {action.variable or ''}"
    if action.type == "set_object_enabled":
        return f"set_object_enabled: {action.object_id or ''}"
    if action.type == "sequence":
        return f"sequence: {len(action.actions)} actions"
    if action.type == "conditional":
        return f"conditional: {len(action.if_actions)} if / {len(action.else_actions)} else"
    if action.type == "move_player":
        return f"move_player: {len(action.path)} points"
    return action.type
