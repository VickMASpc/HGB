from __future__ import annotations

from pathlib import Path

from pce.shared.models import Condition, RuntimeState
from pce.shared.schema import runtime_state_from_dict, to_plain_data
from pce.shared.serialization import load_json, write_json


def object_key(scene_id: str, object_id: str) -> str:
    return f"{scene_id}:{object_id}"


def evaluate_condition(state: RuntimeState, condition: Condition | None, scene_id: str) -> bool:
    if condition is None or condition.type == "always":
        return True
    if condition.type == "not":
        return not evaluate_condition(state, condition.condition, scene_id)
    if condition.type == "has_item":
        return bool(condition.item and condition.item in state.inventory)
    if condition.type == "object_enabled":
        if not condition.object_id:
            return False
        return state.object_enabled.get(object_key(scene_id, condition.object_id), True)
    if condition.type == "variable":
        left = state.variables.get(condition.variable or "")
        right = condition.value
        if condition.operator == "!=":
            return left != right
        if condition.operator == ">":
            return left is not None and left > right
        if condition.operator == "<":
            return left is not None and left < right
        if condition.operator == ">=":
            return left is not None and left >= right
        if condition.operator == "<=":
            return left is not None and left <= right
        return left == right
    return False


def save_state(project_root: Path, slot: str, state: RuntimeState) -> Path:
    safe_slot = _safe_slot(slot)
    path = project_root / "saves" / f"{safe_slot}.json"
    write_json(path, state)
    return path


def load_state(project_root: Path, slot: str) -> RuntimeState:
    safe_slot = _safe_slot(slot)
    return runtime_state_from_dict(load_json(project_root / "saves" / f"{safe_slot}.json"))


def list_save_slots(project_root: Path) -> list[str]:
    save_dir = project_root / "saves"
    if not save_dir.exists():
        return []
    return sorted(path.stem for path in save_dir.glob("*.json"))


def state_to_dict(state: RuntimeState) -> dict:
    return to_plain_data(state)


def _safe_slot(slot: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in {"_", "-"} else "_" for char in slot.strip())
    return cleaned or "slot_1"
