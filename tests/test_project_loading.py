from __future__ import annotations

from pathlib import Path

from pce.shared.serialization import load_project, load_scenes
from pce.shared.validation import validate_project_folder


def test_loads_valid_project(sample_project: Path) -> None:
    project = load_project(sample_project)
    scenes = load_scenes(sample_project, project)
    assert project.title == "Mini Adventure"
    assert project.schema_version == 2
    assert project.items[0].id == "clubhouse_key"
    assert set(scenes) == {"town_square", "clubhouse", "garage"}


def test_rejects_missing_game_json(tmp_path: Path) -> None:
    issues = validate_project_folder(tmp_path)
    assert issues[0].code == "MISSING_GAME_JSON"


def test_rejects_missing_start_scene(sample_project: Path) -> None:
    game_path = sample_project / "game.json"
    text = game_path.read_text(encoding="utf-8").replace('"start_scene": "town_square"', '"start_scene": "missing"')
    game_path.write_text(text, encoding="utf-8")
    issues = validate_project_folder(sample_project)
    assert any(issue.code == "MISSING_START_SCENE" for issue in issues)


def test_rejects_v1_schema(sample_project: Path) -> None:
    game_path = sample_project / "game.json"
    game_path.write_text(game_path.read_text(encoding="utf-8").replace('"schema_version": 2', '"schema_version": 1'), encoding="utf-8")
    issues = validate_project_folder(sample_project)
    assert any(issue.code == "INVALID_SCHEMA_VERSION" for issue in issues)

