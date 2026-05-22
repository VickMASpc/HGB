from __future__ import annotations

from pathlib import Path

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
    text = scene_path.read_text(encoding="utf-8").replace('"walk_path": [[500, 390], [720, 385], [875, 370]],', '"walk_path": [],')
    scene_path.write_text(text, encoding="utf-8")
    project = load_project(sample_project)
    issues = validate_project(sample_project, project, load_scenes(sample_project, project))
    assert any(issue.code == "EXIT_WITHOUT_WALK_PATH" for issue in issues)

