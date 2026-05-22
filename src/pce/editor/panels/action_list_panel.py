from __future__ import annotations

import copy
import json
from typing import Any

from pce.shared.models import Action, Condition
from pce.shared.schema import action_from_dict, condition_from_dict, to_plain_data


ACTION_TYPES = [
    "say",
    "dialogue",
    "move_player",
    "change_scene",
    "sequence",
    "set_variable",
    "give_item",
    "remove_item",
    "set_object_enabled",
    "conditional",
]


def action_to_json(actions: list[Action]) -> str:
    return json.dumps(to_plain_data(actions), indent=2)


def condition_to_json(condition: Condition | None) -> str:
    return json.dumps(to_plain_data(condition or Condition()), indent=2)


def actions_from_json(value: str) -> list[Action]:
    if not value.strip():
        return []
    raw = json.loads(value)
    if not isinstance(raw, list):
        raise ValueError("Expected a JSON array of actions.")
    return [action_from_dict(action) for action in raw]


def condition_from_json(value: str) -> Condition | None:
    if not value.strip():
        return None
    raw = json.loads(value)
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError("Expected a JSON object condition.")
    return condition_from_dict(raw)


def parse_action_value(value: str) -> Any:
    text = value.strip()
    if text.lower() == "true":
        return True
    if text.lower() == "false":
        return False
    if text.lower() == "null":
        return None
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        return value


def merge_action_from_fields(
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
    actions_json: str = "",
    condition_json: str = "",
    if_actions_json: str = "",
    else_actions_json: str = "",
) -> Action:
    if action_type not in ACTION_TYPES:
        raise ValueError(f"Unknown action type: {action_type}")

    action = copy.deepcopy(existing) if existing is not None else Action(type=action_type)
    if action.type != action_type:
        action = Action(type=action_type)
    else:
        action = copy.deepcopy(action)

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
        action.actions = actions_from_json(actions_json) if actions_json.strip() else action.actions
    elif action_type == "set_variable":
        action.variable = variable or None
        action.value = parse_action_value(value)
    elif action_type in {"give_item", "remove_item"}:
        action.item = item or None
    elif action_type == "set_object_enabled":
        action.object_id = object_id or None
        action.enabled = enabled
    elif action_type == "conditional":
        action.condition = condition_from_json(condition_json) or action.condition or Condition()
        if if_actions_json.strip():
            action.if_actions = actions_from_json(if_actions_json)
        if else_actions_json.strip():
            action.else_actions = actions_from_json(else_actions_json)
    return action
