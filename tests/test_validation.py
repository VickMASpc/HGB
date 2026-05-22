from __future__ import annotations

from pathlib import Path

from pce.shared.serialization import load_project, load_scenes
from pce.shared.validation import validate_project


def _codes(sample_project: Path) -> set[str]:
    project = load_project(sample_project)
    return {issue.code for issue in validate_project(sample_project, project, load_scenes(sample_project, project))}


def test_detects_broken_target_scene(sample_project: Path) -> None:
    path = sample_project / "scenes/town_square.json"
    path.write_text(path.read_text(encoding="utf-8").replace('"target_scene": "clubhouse"', '"target_scene": "missing"'), encoding="utf-8")
    assert "MISSING_TARGET_SCENE" in _codes(sample_project)


def test_detects_missing_target_spawn(sample_project: Path) -> None:
    path = sample_project / "scenes/town_square.json"
    path.write_text(path.read_text(encoding="utf-8").replace('"target_spawn": "entrance"', '"target_spawn": "missing"'), encoding="utf-8")
    assert "MISSING_TARGET_SPAWN" in _codes(sample_project)


def test_detects_duplicate_ids(sample_project: Path) -> None:
    path = sample_project / "scenes/town_square.json"
    path.write_text(path.read_text(encoding="utf-8").replace('"id": "mailbox"', '"id": "dog"', 1), encoding="utf-8")
    assert "DUPLICATE_ID" in _codes(sample_project)


def test_detects_bad_rectangles(sample_project: Path) -> None:
    path = sample_project / "scenes/town_square.json"
    path.write_text(path.read_text(encoding="utf-8").replace('"rect": [420, 260, 120, 150]', '"rect": [420, 260, 0, 150]'), encoding="utf-8")
    assert "INVALID_RECT" in _codes(sample_project)


def test_detects_missing_asset_paths(sample_project: Path) -> None:
    (sample_project / "assets/sprites/dog.png").unlink()
    assert "MISSING_NPC_SPRITE" in _codes(sample_project)

