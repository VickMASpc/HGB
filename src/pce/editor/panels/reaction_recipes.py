from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Literal

from pce.editor.panels.dialogue_studio import condition_label
from pce.shared.models import Action, Condition, SceneConfig, Severity, ValidationIssue


RecipeKind = Literal[
    "say",
    "dialogue",
    "give_item",
    "remove_object",
    "change_scene",
    "conditional",
]

RECIPE_TEMPLATES: dict[str, RecipeKind] = {
    "Player says...": "say",
    "Start conversation...": "dialogue",
    "Give item...": "give_item",
    "Remove this object...": "remove_object",
    "Go to scene...": "change_scene",
    "Only if...": "conditional",
}


@dataclass(slots=True)
class SceneConnection:
    source_scene: str
    target_scene: str
    label: str
    object_id: str
    kind: str


def recipe_label(action: Action, *, owner_id: str | None = None) -> str:
    if action.type == "say":
        speaker = action.speaker or "Player"
        line = _short(action.text or "New line")
        return f'{speaker} says "{line}"'
    if action.type == "dialogue":
        target = action.npc or "NPC"
        node = f" at {action.node}" if action.node else ""
        return f"Start conversation with {target}{node}"
    if action.type == "give_item":
        return f"Give item {action.item or 'item'}"
    if action.type == "remove_item":
        return f"Remove item {action.item or 'item'}"
    if action.type == "set_object_enabled" and action.enabled is False:
        if owner_id is not None and action.object_id == owner_id:
            return "Remove this object"
        return f"Remove object {action.object_id or 'object'}"
    if action.type == "set_object_enabled":
        state = "Show" if action.enabled else "Hide"
        return f"{state} object {action.object_id or 'object'}"
    if action.type == "change_scene":
        destination = action.scene or "scene"
        spawn = f" at {action.spawn}" if action.spawn else ""
        return f"Go to scene {destination}{spawn}"
    if action.type == "conditional":
        return f"Only if {condition_label(action.condition)}: {len(action.if_actions)} reaction(s)"
    if action.type == "sequence":
        return f"Do {len(action.actions)} reaction(s) in order"
    if action.type == "set_variable":
        return f"Set {action.variable or 'variable'} to {action.value}"
    if action.type == "move_player":
        return f"Move player through {len(action.path)} point(s)"
    return action.type.replace("_", " ").title()


def numbered_recipe_labels(actions: list[Action], *, owner_id: str | None = None) -> list[str]:
    return [f"{index + 1}. {recipe_label(action, owner_id=owner_id)}" for index, action in enumerate(actions)]


def default_action_for_recipe(
    recipe: RecipeKind,
    *,
    owner_id: str | None = None,
    current_scene: SceneConfig | None = None,
) -> Action:
    if recipe == "say":
        return Action(type="say", speaker="Player", text="New line.")
    if recipe == "dialogue":
        npc_id = _first_npc_id(current_scene) or owner_id
        return Action(type="dialogue", npc=npc_id)
    if recipe == "give_item":
        return Action(type="give_item")
    if recipe == "remove_object":
        return Action(type="set_object_enabled", object_id=owner_id, enabled=False)
    if recipe == "change_scene":
        target = current_scene.id if current_scene is not None else None
        spawn = current_scene.spawns[0].id if current_scene is not None and current_scene.spawns else None
        return Action(type="change_scene", scene=target, spawn=spawn)
    if recipe == "conditional":
        return Action(
            type="conditional",
            condition=Condition(type="always"),
            if_actions=[Action(type="say", speaker="Player", text="New line.")],
        )
    raise ValueError(f"Unknown recipe: {recipe}")


def duplicate_action(action: Action) -> Action:
    return copy.deepcopy(action)


def scene_card_label(scene: SceneConfig) -> str:
    return f"{scene.name} ({scene.id})"


def scene_id_from_card_label(label: str, scenes: dict[str, SceneConfig]) -> str:
    for scene_id, scene in scenes.items():
        if label == scene_card_label(scene):
            return scene_id
    return label.rsplit("(", 1)[-1].rstrip(")") if "(" in label else label


def scene_card_labels(scenes: dict[str, SceneConfig]) -> list[str]:
    return [scene_card_label(scene) for scene in scenes.values()]


def collect_scene_connections(scenes: dict[str, SceneConfig]) -> list[SceneConnection]:
    connections: list[SceneConnection] = []
    for scene_id, scene in scenes.items():
        for exit_data in scene.exits:
            connections.append(
                SceneConnection(
                    source_scene=scene_id,
                    target_scene=exit_data.target_scene,
                    label=exit_data.name,
                    object_id=exit_data.id,
                    kind="exit",
                )
            )
        for kind, owner_id, actions in _iter_action_owners(scene):
            for action in _iter_actions(actions):
                if action.type == "change_scene" and action.scene:
                    connections.append(
                        SceneConnection(
                            source_scene=scene_id,
                            target_scene=action.scene,
                            label=recipe_label(action, owner_id=owner_id),
                            object_id=owner_id,
                            kind=kind,
                        )
                    )
    return connections


def story_map_lines(scenes: dict[str, SceneConfig]) -> list[str]:
    if not scenes:
        return []
    connections = collect_scene_connections(scenes)
    if not connections:
        return [f"{scene.name} ({scene.id}) has no outgoing scene links." for scene in scenes.values()]
    return [
        f"{scenes.get(item.source_scene, SceneConfig(2, item.source_scene, item.source_scene, '')).name}"
        f" -> {scenes.get(item.target_scene, SceneConfig(2, item.target_scene, item.target_scene, '')).name}"
        f" via {item.label}"
        for item in connections
    ]


def recipe_validation_warnings(
    object_id: str,
    actions: list[Action],
    issues: list[ValidationIssue],
) -> dict[int, list[str]]:
    warnings: dict[int, list[str]] = {}
    object_messages = [
        issue.message
        for issue in issues
        if issue.object_id == object_id and issue.severity in {Severity.ERROR, Severity.WARNING}
    ]
    for index, action in enumerate(actions):
        messages = _local_action_warnings(action)
        messages.extend(_matching_issue_messages(action, object_messages))
        if messages:
            warnings[index] = messages
    return warnings


def exit_validation_warnings(object_id: str, issues: list[ValidationIssue]) -> list[str]:
    return [
        issue.message
        for issue in issues
        if issue.object_id == object_id and issue.severity in {Severity.ERROR, Severity.WARNING}
    ]


def _local_action_warnings(action: Action) -> list[str]:
    warnings: list[str] = []
    if action.type == "say" and not action.text:
        warnings.append("Add the line the player or character should say.")
    if action.type == "dialogue" and not action.npc:
        warnings.append("Choose the NPC conversation to start.")
    if action.type == "give_item" and not action.item:
        warnings.append("Choose the inventory item to give.")
    if action.type == "remove_item" and not action.item:
        warnings.append("Choose the inventory item to remove.")
    if action.type == "set_object_enabled" and not action.object_id:
        warnings.append("Choose the object this recipe changes.")
    if action.type == "change_scene":
        if not action.scene:
            warnings.append("Choose the destination scene.")
        if not action.spawn:
            warnings.append("Choose where the player appears.")
    if action.type == "conditional" and action.condition in {None, Condition(type="always")}:
        warnings.append("Choose a condition for this recipe.")
    return warnings


def _matching_issue_messages(action: Action, messages: list[str]) -> list[str]:
    matched: list[str] = []
    for message in messages:
        if action.type in message or (action.scene and action.scene in message) or (action.item and action.item in message):
            matched.append(message)
    return matched


def _iter_action_owners(scene: SceneConfig):
    for item in scene.hotspots:
        yield "hotspot", item.id, item.on_click
    for item in scene.npcs:
        yield "npc", item.id, item.on_click
    for item in scene.items:
        yield "item", item.id, item.on_click


def _iter_actions(actions: list[Action]):
    for action in actions:
        yield action
        yield from _iter_actions(action.actions)
        yield from _iter_actions(action.if_actions)
        yield from _iter_actions(action.else_actions)


def _first_npc_id(scene: SceneConfig | None) -> str | None:
    return scene.npcs[0].id if scene is not None and scene.npcs else None


def _short(value: str, limit: int = 42) -> str:
    text = " ".join(value.split())
    return text if len(text) <= limit else f"{text[: limit - 1]}..."
