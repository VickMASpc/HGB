from __future__ import annotations

import json
from pathlib import Path

from pce.shared.models import Action
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
    data = json.loads(path.read_text(encoding="utf-8"))
    data["hotspots"][0]["rect"] = [420, 260, 0, 150]
    path.write_text(json.dumps(data), encoding="utf-8")
    assert "INVALID_RECT" in _codes(sample_project)


def test_detects_missing_asset_paths(sample_project: Path) -> None:
    (sample_project / "assets/sprites/dog1.png").unlink()
    assert "MISSING_NPC_SPRITE" in _codes(sample_project)


def test_detects_missing_item_definition(sample_project: Path) -> None:
    path = sample_project / "scenes/town_square.json"
    path.write_text(path.read_text(encoding="utf-8").replace('"item_id": "clubhouse_key"', '"item_id": "missing"'), encoding="utf-8")
    assert "MISSING_ITEM_DEFINITION" in _codes(sample_project)


def test_detects_broken_dialogue_node(sample_project: Path) -> None:
    path = sample_project / "scenes/town_square.json"
    path.write_text(path.read_text(encoding="utf-8").replace('"target": "hint"', '"target": "missing"'), encoding="utf-8")
    assert "MISSING_DIALOGUE_NODE" in _codes(sample_project)


def test_detects_invalid_variable_name(sample_project: Path) -> None:
    path = sample_project / "scenes/town_square.json"
    path.write_text(path.read_text(encoding="utf-8").replace('"variable": "found_key"', '"variable": "1bad"'), encoding="utf-8")
    assert "INVALID_VARIABLE_NAME" in _codes(sample_project)


def test_rejects_blocking_dialogue_node_effect(sample_project: Path) -> None:
    project = load_project(sample_project)
    scenes = load_scenes(sample_project, project)
    scenes["town_square"].npcs[0].dialogue_nodes[0].actions = [
        Action(type="dialogue", npc="dog", node="hello")
    ]

    issues = validate_project(sample_project, project, scenes)

    assert any(issue.code == "UNSUPPORTED_DIALOGUE_NODE_EFFECT" for issue in issues)


def test_dialogue_graph_reports_blank_content_duplicates_and_unreachable_nodes(
    sample_project: Path,
) -> None:
    project = load_project(sample_project)
    scenes = load_scenes(sample_project, project)
    npc = scenes["town_square"].npcs[0]
    node_type = npc.dialogue_nodes[0].__class__
    choice_type = npc.dialogue_nodes[0].choices[0].__class__
    npc.dialogue_nodes.extend(
        [
            node_type(id="", speaker="Dog", text=""),
            node_type(id="hello", speaker="Dog", text="Duplicate"),
            node_type(
                id="orphan",
                speaker="Dog",
                text="Valid but unreachable",
                choices=[choice_type(text="", target="missing")],
            ),
        ]
    )

    issues = validate_project(sample_project, project, scenes)
    severities = {issue.code: issue.severity.value for issue in issues}

    assert severities["EMPTY_DIALOGUE_NODE_ID"] == "ERROR"
    assert severities["EMPTY_DIALOGUE_NODE_TEXT"] == "ERROR"
    assert severities["EMPTY_DIALOGUE_CHOICE_TEXT"] == "ERROR"
    assert severities["MISSING_DIALOGUE_NODE"] == "ERROR"
    assert severities["DUPLICATE_DIALOGUE_NODE"] == "ERROR"
    assert severities["UNREACHABLE_DIALOGUE_NODE"] == "WARNING"


def test_dialogue_action_validates_npc_node_and_fallback(sample_project: Path) -> None:
    project = load_project(sample_project)
    scenes = load_scenes(sample_project, project)
    scene = scenes["town_square"]
    scene.hotspots[0].on_click = [
        Action(type="dialogue", npc="missing", node="hello"),
        Action(type="dialogue", npc="dog", node="missing"),
    ]
    scene.npcs[0].lines = []
    scene.hotspots[1].on_click = [Action(type="dialogue", npc="dog")]

    issues = validate_project(sample_project, project, scenes)
    codes = {issue.code for issue in issues}

    assert "MISSING_DIALOGUE_NPC_REFERENCE" in codes
    assert "MISSING_DIALOGUE_ACTION_NODE" in codes
    assert "EMPTY_DIALOGUE_ACTION" in codes
