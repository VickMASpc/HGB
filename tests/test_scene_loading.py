from __future__ import annotations

import json
from pathlib import Path

from pce.runtime.scene_runtime import SceneRuntime, npc_rect, visible_items, visible_npcs
from pce.runtime.state import object_key
from pce.shared.models import RuntimeState
from pce.shared.serialization import load_project, load_scene, load_scenes
from pce.shared.validation import validate_project


def test_loads_valid_scene(sample_project: Path) -> None:
    scene = load_scene(sample_project, "scenes/town_square.json")
    assert scene.id == "town_square"
    assert scene.hotspots[0].id == "mailbox"
    assert scene.items[0].item_id == "clubhouse_key"
    assert scene.npcs[0].dialogue_nodes[0].id == "hello"


def test_rejects_missing_background(sample_project: Path) -> None:
    (sample_project / "assets/backgrounds/town_square.png").unlink()
    project = load_project(sample_project)
    issues = validate_project(sample_project, project, load_scenes(sample_project, project))
    assert any(issue.code == "MISSING_BACKGROUND" for issue in issues)


def test_validates_spawn_points(sample_project: Path) -> None:
    scene_path = sample_project / "scenes/garage.json"
    text = scene_path.read_text(encoding="utf-8").replace('"spawns": [', '"spawns": [], "unused": [')
    scene_path.write_text(text, encoding="utf-8")
    project = load_project(sample_project)
    issues = validate_project(sample_project, project, load_scenes(sample_project, project))
    assert any(issue.code == "SCENE_WITHOUT_SPAWN" for issue in issues)


def test_validates_exits(sample_project: Path) -> None:
    scene_path = sample_project / "scenes/town_square.json"
    data = json.loads(scene_path.read_text(encoding="utf-8"))
    data["exits"][0]["walk_path"] = []
    scene_path.write_text(json.dumps(data), encoding="utf-8")
    project = load_project(sample_project)
    issues = validate_project(sample_project, project, load_scenes(sample_project, project))
    assert any(issue.code == "EXIT_WITHOUT_WALK_PATH" for issue in issues)


def test_disabled_item_is_not_visible_or_clickable(sample_project: Path) -> None:
    scene = load_scene(sample_project, "scenes/town_square.json")
    item = scene.items[0]
    state = RuntimeState(scene.id, (0, 0), object_enabled={object_key(scene.id, item.id): False})

    assert item not in visible_items(scene, state)
    assert SceneRuntime(scene, state).hit_test((item.rect[0] + 1, item.rect[1] + 1)) is None


def test_disabled_npc_is_not_visible_or_clickable(sample_project: Path) -> None:
    scene = load_scene(sample_project, "scenes/town_square.json")
    npc = scene.npcs[0]
    state = RuntimeState(scene.id, (0, 0), object_enabled={object_key(scene.id, npc.id): False})
    rect = npc_rect(npc)

    assert npc not in visible_npcs(scene, state)
    assert SceneRuntime(scene, state).hit_test((rect[0] + 1, rect[1] + 1)) is None
