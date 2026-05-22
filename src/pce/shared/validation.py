from __future__ import annotations

from collections import Counter
from pathlib import Path

from pce.shared.asset_paths import project_path
from pce.shared.constants import SCHEMA_VERSION
from pce.shared.models import Action, Condition, ProjectConfig, SceneConfig, Severity, ValidationIssue
from pce.shared.serialization import load_project, load_scenes


def _issue(
    severity: Severity,
    code: str,
    message: str,
    file: str | None = None,
    object_id: str | None = None,
) -> ValidationIssue:
    return ValidationIssue(severity, code, message, file, object_id)


def _asset_issue(project_root: Path, relative_path: str, code: str, file: str, object_id: str) -> ValidationIssue | None:
    try:
        path = project_path(project_root, relative_path)
    except ValueError as exc:
        return _issue(Severity.ERROR, "ABSOLUTE_ASSET_PATH", str(exc), file, object_id)
    if not path.exists():
        return _issue(Severity.ERROR, code, f"Missing asset '{relative_path}'.", file, object_id)
    return None


def validate_project_folder(project_root: Path) -> list[ValidationIssue]:
    game_path = project_root / "game.json"
    if not game_path.exists():
        return [
            _issue(
                Severity.ERROR,
                "MISSING_GAME_JSON",
                f"Missing game.json in project folder '{project_root}'.",
                "game.json",
            )
        ]
    try:
        project = load_project(project_root)
        scenes = load_scenes(project_root, project)
    except Exception as exc:
        return [_issue(Severity.ERROR, "LOAD_FAILED", str(exc))]
    return validate_project(project_root, project, scenes)


def validate_project(
    project_root: Path,
    project: ProjectConfig,
    scenes: dict[str, SceneConfig],
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if project.schema_version != SCHEMA_VERSION:
        issues.append(
            _issue(
                Severity.ERROR,
                "INVALID_SCHEMA_VERSION",
                f"Expected schema_version {SCHEMA_VERSION}, got {project.schema_version}.",
                "game.json",
            )
        )

    listed_scene_ids: set[str] = set()
    for scene_file in project.scenes:
        scene_path = project_root / scene_file
        if not scene_path.exists():
            issues.append(
                _issue(
                    Severity.ERROR,
                    "MISSING_SCENE_FILE",
                    f"Scene file listed in game.json does not exist: {scene_file}.",
                    "game.json",
                )
            )
            continue
        scene = scenes.get(Path(scene_file).stem)
        if scene is None:
            continue
        listed_scene_ids.add(scene.id)
        if Path(scene_file).stem != scene.id:
            issues.append(
                _issue(
                    Severity.ERROR,
                    "SCENE_ID_MISMATCH",
                    f"Scene file '{scene_file}' contains id '{scene.id}'.",
                    scene_file,
                    scene.id,
                )
            )

    if project.start_scene not in scenes:
        issues.append(
            _issue(
                Severity.ERROR,
                "MISSING_START_SCENE",
                f"Start scene '{project.start_scene}' is not present in project scenes.",
                "game.json",
            )
        )

    player_asset = _asset_issue(
        project_root,
        project.player.sprite,
        "MISSING_PLAYER_SPRITE",
        "game.json",
        "player",
    )
    if player_asset:
        issues.append(player_asset)

    item_ids = [item.id for item in project.items]
    for item_id, count in Counter(item_ids).items():
        if item_id and count > 1:
            issues.append(_issue(Severity.ERROR, "DUPLICATE_ITEM_ID", f"Duplicate item id '{item_id}'.", "game.json", item_id))
    for item in project.items:
        if item.sprite:
            item_asset = _asset_issue(project_root, item.sprite, "MISSING_ITEM_SPRITE", "game.json", item.id)
            if item_asset:
                issues.append(item_asset)

    for scene_file in project.scenes:
        scene = scenes.get(Path(scene_file).stem)
        if scene is None:
            continue
        issues.extend(validate_scene(project_root, scene_file, scene, scenes, set(item_ids)))

    return issues


def validate_scene(
    project_root: Path,
    scene_file: str,
    scene: SceneConfig,
    scenes: dict[str, SceneConfig],
    item_ids: set[str] | None = None,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if scene.schema_version != SCHEMA_VERSION:
        issues.append(
            _issue(
                Severity.ERROR,
                "INVALID_SCHEMA_VERSION",
                f"Scene '{scene.id}' has invalid schema_version {scene.schema_version}.",
                scene_file,
                scene.id,
            )
        )
    if not scene.spawns:
        issues.append(
            _issue(
                Severity.ERROR,
                "SCENE_WITHOUT_SPAWN",
                f"Scene '{scene.id}' has no spawn point.",
                scene_file,
                scene.id,
            )
        )

    background_issue = _asset_issue(
        project_root,
        scene.background,
        "MISSING_BACKGROUND",
        scene_file,
        scene.id,
    )
    if background_issue:
        issues.append(background_issue)

    item_ids = item_ids or set()
    ids = [item.id for item in [*scene.spawns, *scene.hotspots, *scene.exits, *scene.npcs, *scene.items]]
    for object_id, count in Counter(ids).items():
        if object_id and count > 1:
            issues.append(
                _issue(
                    Severity.ERROR,
                    "DUPLICATE_ID",
                    f"Duplicate id '{object_id}' in scene '{scene.id}'.",
                    scene_file,
                    object_id,
                )
            )

    spawn_ids = {spawn.id for spawn in scene.spawns}
    npc_ids = {npc.id for npc in scene.npcs}
    scene_object_ids = set(ids)
    for hotspot in scene.hotspots:
        x, y, width, height = hotspot.rect
        if width <= 0 or height <= 0:
            issues.append(
                _issue(
                    Severity.ERROR,
                    "INVALID_RECT",
                    f"Hotspot '{hotspot.id}' has invalid rect {hotspot.rect}.",
                    scene_file,
                    hotspot.id,
                )
            )
        issues.extend(_validate_actions(scene_file, hotspot.id, hotspot.on_click, scenes, spawn_ids, npc_ids, item_ids, scene_object_ids))

    for exit_data in scene.exits:
        x, y, width, height = exit_data.rect
        if width <= 0 or height <= 0:
            issues.append(
                _issue(
                    Severity.ERROR,
                    "INVALID_RECT",
                    f"Exit '{exit_data.id}' has invalid rect {exit_data.rect}.",
                    scene_file,
                    exit_data.id,
                )
            )
        if not exit_data.walk_path:
            issues.append(
                _issue(
                    Severity.ERROR,
                    "EXIT_WITHOUT_WALK_PATH",
                    f"Exit '{exit_data.id}' must define a walk_path.",
                    scene_file,
                    exit_data.id,
                )
            )
        if exit_data.target_scene not in scenes:
            issues.append(
                _issue(
                    Severity.ERROR,
                    "MISSING_TARGET_SCENE",
                    f"Exit '{exit_data.id}' references missing scene '{exit_data.target_scene}'.",
                    scene_file,
                    exit_data.id,
                )
            )
        elif exit_data.target_spawn not in {spawn.id for spawn in scenes[exit_data.target_scene].spawns}:
            issues.append(
                _issue(
                    Severity.ERROR,
                    "MISSING_TARGET_SPAWN",
                    f"Exit '{exit_data.id}' references missing spawn '{exit_data.target_spawn}'.",
                    scene_file,
                    exit_data.id,
                )
            )

    for npc in scene.npcs:
        if npc.sprite:
            sprite_issue = _asset_issue(project_root, npc.sprite, "MISSING_NPC_SPRITE", scene_file, npc.id)
            if sprite_issue:
                issues.append(sprite_issue)
        node_ids = {node.id for node in npc.dialogue_nodes}
        for node_id, count in Counter(node_ids).items():
            if node_id and count > 1:
                issues.append(_issue(Severity.ERROR, "DUPLICATE_DIALOGUE_NODE", f"Duplicate dialogue node '{node_id}'.", scene_file, npc.id))
        for node in npc.dialogue_nodes:
            issues.extend(_validate_actions(scene_file, npc.id, node.actions, scenes, spawn_ids, npc_ids, item_ids, scene_object_ids))
            for choice in node.choices:
                if choice.target and choice.target not in node_ids:
                    issues.append(_issue(Severity.ERROR, "MISSING_DIALOGUE_NODE", f"Choice references missing dialogue node '{choice.target}'.", scene_file, npc.id))
                issues.extend(_validate_condition(scene_file, npc.id, choice.condition, item_ids, scene_object_ids))
                issues.extend(_validate_actions(scene_file, npc.id, choice.actions, scenes, spawn_ids, npc_ids, item_ids, scene_object_ids))
        issues.extend(_validate_actions(scene_file, npc.id, npc.on_click, scenes, spawn_ids, npc_ids, item_ids, scene_object_ids))

    for item in scene.items:
        x, y, width, height = item.rect
        if width <= 0 or height <= 0:
            issues.append(_issue(Severity.ERROR, "INVALID_RECT", f"Item '{item.id}' has invalid rect {item.rect}.", scene_file, item.id))
        if item.item_id not in item_ids:
            issues.append(_issue(Severity.ERROR, "MISSING_ITEM_DEFINITION", f"Scene item '{item.id}' references missing item '{item.item_id}'.", scene_file, item.id))
        issues.extend(_validate_actions(scene_file, item.id, item.on_click, scenes, spawn_ids, npc_ids, item_ids, scene_object_ids))

    return issues


def _validate_actions(
    scene_file: str,
    object_id: str,
    actions: list[Action],
    scenes: dict[str, SceneConfig],
    spawn_ids: set[str],
    npc_ids: set[str],
    item_ids: set[str],
    scene_object_ids: set[str],
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for action in actions:
        if action.type == "dialogue" and (not action.npc or action.npc not in npc_ids):
            issues.append(
                _issue(
                    Severity.ERROR,
                    "MISSING_DIALOGUE_NPC_REFERENCE",
                    f"Action on '{object_id}' references missing NPC '{action.npc}'.",
                    scene_file,
                    object_id,
                )
            )
        if action.type == "change_scene":
            if not action.scene or action.scene not in scenes:
                issues.append(
                    _issue(
                        Severity.ERROR,
                        "MISSING_ACTION_TARGET",
                        f"change_scene action references missing scene '{action.scene}'.",
                        scene_file,
                        object_id,
                    )
                )
            elif action.spawn not in {spawn.id for spawn in scenes[action.scene].spawns}:
                issues.append(
                    _issue(
                        Severity.ERROR,
                        "MISSING_ACTION_TARGET",
                        f"change_scene action references missing spawn '{action.spawn}'.",
                        scene_file,
                        object_id,
                    )
                )
        if action.type == "move_player" and any(len(point) != 2 for point in action.path):
            issues.append(
                _issue(
                    Severity.ERROR,
                    "INVALID_PATH_POINT",
                    f"move_player action on '{object_id}' has an invalid path point.",
                    scene_file,
                    object_id,
                )
            )
        if action.type == "sequence":
            issues.extend(_validate_actions(scene_file, object_id, action.actions, scenes, spawn_ids, npc_ids, item_ids, scene_object_ids))
        if action.type in {"give_item", "remove_item"} and action.item not in item_ids:
            issues.append(_issue(Severity.ERROR, "MISSING_ACTION_ITEM", f"Action references missing item '{action.item}'.", scene_file, object_id))
        if action.type == "set_object_enabled" and action.object_id not in scene_object_ids:
            issues.append(_issue(Severity.ERROR, "MISSING_ACTION_OBJECT", f"Action references missing object '{action.object_id}'.", scene_file, object_id))
        if action.type == "set_variable" and not _valid_variable_name(action.variable):
            issues.append(_issue(Severity.ERROR, "INVALID_VARIABLE_NAME", f"Invalid variable name '{action.variable}'.", scene_file, object_id))
        if action.type == "conditional":
            issues.extend(_validate_condition(scene_file, object_id, action.condition, item_ids, scene_object_ids))
            issues.extend(_validate_actions(scene_file, object_id, action.if_actions, scenes, spawn_ids, npc_ids, item_ids, scene_object_ids))
            issues.extend(_validate_actions(scene_file, object_id, action.else_actions, scenes, spawn_ids, npc_ids, item_ids, scene_object_ids))
    return issues


def _validate_condition(
    scene_file: str,
    object_id: str,
    condition: Condition | None,
    item_ids: set[str],
    scene_object_ids: set[str],
) -> list[ValidationIssue]:
    if condition is None or condition.type == "always":
        return []
    issues: list[ValidationIssue] = []
    if condition.type == "variable" and not _valid_variable_name(condition.variable):
        issues.append(_issue(Severity.ERROR, "INVALID_VARIABLE_NAME", f"Invalid condition variable '{condition.variable}'.", scene_file, object_id))
    if condition.type == "has_item" and condition.item not in item_ids:
        issues.append(_issue(Severity.ERROR, "MISSING_CONDITION_ITEM", f"Condition references missing item '{condition.item}'.", scene_file, object_id))
    if condition.type == "object_enabled" and condition.object_id not in scene_object_ids:
        issues.append(_issue(Severity.ERROR, "MISSING_CONDITION_OBJECT", f"Condition references missing object '{condition.object_id}'.", scene_file, object_id))
    if condition.type == "not":
        issues.extend(_validate_condition(scene_file, object_id, condition.condition, item_ids, scene_object_ids))
    return issues


def _valid_variable_name(value: str | None) -> bool:
    if not value:
        return False
    return value.replace("_", "").isalnum() and not value[0].isdigit()


def has_errors(issues: list[ValidationIssue]) -> bool:
    return any(issue.severity == Severity.ERROR for issue in issues)

