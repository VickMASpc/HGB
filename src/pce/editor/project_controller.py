from __future__ import annotations

import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from pce.shared.constants import DEFAULT_LAYERS
from pce.shared.models import Action, Exit, Hotspot, NPC, ProjectConfig, SceneConfig, SpawnPoint
from pce.shared.serialization import autosave_project, create_project, load_project, load_scenes, save_project
from pce.shared.schema import scene_from_dict
from pce.shared.validation import ValidationIssue, validate_project


class ProjectController:
    def __init__(self) -> None:
        self.project_root: Path | None = None
        self.project: ProjectConfig | None = None
        self.scenes: dict[str, SceneConfig] = {}
        self.current_scene_id: str | None = None
        self.last_autosave: Path | None = None
        self._undo_stack: list[tuple[ProjectConfig, dict[str, SceneConfig], str | None]] = []
        self._redo_stack: list[tuple[ProjectConfig, dict[str, SceneConfig], str | None]] = []

    @property
    def current_scene(self) -> SceneConfig | None:
        if self.current_scene_id is None:
            return None
        return self.scenes.get(self.current_scene_id)

    def new_project(self, project_root: Path, title: str = "Mini Adventure") -> None:
        self.project, self.scenes = create_project(project_root, title)
        self.project_root = project_root
        self.current_scene_id = self.project.start_scene
        self._undo_stack.clear()
        self._redo_stack.clear()

    def open_project(self, project_root: Path) -> None:
        self.project_root = project_root
        self.project = load_project(project_root)
        if self.project.schema_version != SCHEMA_VERSION:
            raise ValueError(
                f"PointClick Engine v2 requires schema_version {SCHEMA_VERSION}; "
                f"found {self.project.schema_version}."
            )
        self.scenes = load_scenes(project_root, self.project)
        self.current_scene_id = self.project.start_scene
        self._undo_stack.clear()
        self._redo_stack.clear()

    def save(self) -> None:
        if self.project_root is None or self.project is None:
            raise ValueError("No project is open.")
        save_project(self.project_root, self.project, self.scenes)

    def autosave(self) -> Path:
        if self.project_root is None or self.project is None:
            raise ValueError("No project is open.")
        self.last_autosave = autosave_project(self.project_root, self.project, self.scenes)
        return self.last_autosave

    def validate(self) -> list[ValidationIssue]:
        if self.project_root is None or self.project is None:
            return []
        return validate_project(self.project_root, self.project, self.scenes)

    def create_scene(self, scene_id: str) -> None:
        if self.project is None:
            raise ValueError("No project is open.")
        scene_id = self._clean_id(scene_id or "scene")
        scene_path = f"scenes/{scene_id}.json"
        if scene_path not in self.project.scenes:
            self.project.scenes.append(scene_path)
        self.scenes[scene_id] = SceneConfig(
            schema_version=SCHEMA_VERSION,
            id=scene_id,
            name=scene_id.replace("_", " ").title(),
            background=f"assets/backgrounds/{scene_id}.png",
            layers=scene_from_dict({"layers": DEFAULT_LAYERS}).layers,
            spawns=[SpawnPoint(id="start", position=(120, 400), facing="right")],
        )
        self.current_scene_id = scene_id

    def add_hotspot(self) -> None:
        scene = self._require_scene()
        self.record_undo()
        number = len(scene.hotspots) + 1
        scene.hotspots.append(
            Hotspot(
                id=f"hotspot_{number}",
                name=f"Hotspot {number}",
                rect=(360, 240, 140, 90),
                on_click=[Action(type="say", speaker="Player", text="There is something here.")],
            )
        )

    def add_spawn(self) -> None:
        scene = self._require_scene()
        number = len(scene.spawns) + 1
        scene.spawns.append(SpawnPoint(id=f"spawn_{number}", position=(160, 390), facing="right"))

    def add_exit(self) -> None:
        scene = self._require_scene()
        self.record_undo()
        target_scene = self.project.start_scene if self.project else scene.id
        number = len(scene.exits) + 1
        scene.exits.append(
            Exit(
                id=f"exit_{number}",
                name=f"Exit {number}",
                rect=(840, 240, 80, 220),
                walk_path=[(500, 390), (760, 385), (880, 370)],
                target_scene=target_scene,
                target_spawn="start",
            )
        )

    def add_npc(self) -> None:
        scene = self._require_scene()
        self.record_undo()
        number = len(scene.npcs) + 1
        npc_id = f"npc_{number}"
        scene.npcs.append(
            NPC(
                id=npc_id,
                name=f"NPC {number}",
                sprite=None,
                position=(620, 390),
                lines=["Hello!", "Let's explore."],
                on_click=[Action(type="dialogue", npc=npc_id)],
            )
        )

    def import_asset(self, source: Path, asset_kind: str) -> str:
        if self.project_root is None:
            raise ValueError("No project is open.")
        if not source.exists():
            raise FileNotFoundError(f"Asset does not exist: {source}")
        folder = {
            "background": "assets/backgrounds",
            "sprite": "assets/sprites",
            "ui": "assets/ui",
        }.get(asset_kind, "assets/ui")
        target_dir = self.project_root / folder
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / source.name
        if source.resolve() != target.resolve():
            shutil.copy2(source, target)
        return target.relative_to(self.project_root).as_posix()

    def assign_scene_background(self, relative_path: str) -> None:
        scene = self._require_scene()
        scene.background = relative_path

    def assign_player_sprite(self, relative_path: str) -> None:
        if self.project is None:
            raise ValueError("No project is open.")
        self.project.player.sprite = relative_path

    def assign_npc_sprite(self, npc_id: str, relative_path: str) -> None:
        scene = self._require_scene()
        for npc in scene.npcs:
            if npc.id == npc_id:
                npc.sprite = relative_path
                return
        raise ValueError(f"Unknown NPC: {npc_id}")

    def set_current_scene_as_start(self) -> None:
        if self.project is None or self.current_scene_id is None:
            raise ValueError("No project is open.")
        self.project.start_scene = self.current_scene_id
        self.project.player.default_scene = self.current_scene_id

    @staticmethod
    def _clean_id(value: str) -> str:
        cleaned = "".join(char.lower() if char.isalnum() else "_" for char in value.strip())
        cleaned = "_".join(part for part in cleaned.split("_") if part)
        return cleaned or "item"

    def run_runtime(self, scene_id: str | None = None) -> subprocess.Popen:
        if self.project_root is None:
            raise ValueError("No project is open.")
        command = [
            sys.executable,
            "-m",
            "pce.runtime.main",
            "--project",
            str(self.project_root),
        ]
        if scene_id:
            command.extend(["--scene", scene_id])
        return subprocess.Popen(command)

    def _require_scene(self) -> SceneConfig:
        scene = self.current_scene
        if scene is None:
            raise ValueError("No scene is selected.")
        return scene

