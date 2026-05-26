from __future__ import annotations

import copy
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from pce.shared.constants import DEFAULT_LAYERS, SCHEMA_VERSION
from pce.shared.models import (
    Action,
    Condition,
    DialogueChoice,
    DialogueNode,
    Exit,
    Hotspot,
    ItemDefinition,
    LayerConfig,
    NPC,
    ProjectConfig,
    SceneConfig,
    SceneItem,
    SpawnPoint,
)
from pce.shared.serialization import autosave_project, create_project, load_project, load_scenes, save_project
from pce.shared.schema import scene_from_dict
from pce.shared.validation import ValidationIssue, validate_project


ProjectSnapshot = tuple[ProjectConfig, dict[str, SceneConfig], str | None]
_UNSET = object()


class ProjectController:
    def __init__(self) -> None:
        self.project_root: Path | None = None
        self.project: ProjectConfig | None = None
        self.scenes: dict[str, SceneConfig] = {}
        self.current_scene_id: str | None = None
        self.last_autosave: Path | None = None
        self.is_dirty = False
        self._undo_stack: list[ProjectSnapshot] = []
        self._redo_stack: list[ProjectSnapshot] = []

    @property
    def current_scene(self) -> SceneConfig | None:
        if self.current_scene_id is None:
            return None
        return self.scenes.get(self.current_scene_id)

    def new_project(self, project_root: Path, title: str = "Mini Adventure") -> None:
        self.project, self.scenes = create_project(project_root, title)
        self.project_root = project_root
        self.current_scene_id = self.project.start_scene
        self.is_dirty = False
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
        self.is_dirty = False
        self._undo_stack.clear()
        self._redo_stack.clear()

    def save(self) -> None:
        if self.project_root is None or self.project is None:
            raise ValueError("No project is open.")
        save_project(self.project_root, self.project, self.scenes)
        self.is_dirty = False

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
        scene_id = self._unique_scene_id(scene_id or "scene")
        scene_path = f"scenes/{scene_id}.json"
        self.record_undo()
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
        object_id = self._unique_object_id(scene, "hotspot", f"hotspot_{number}")
        scene.hotspots.append(
            Hotspot(
                id=object_id,
                name=f"Hotspot {number}",
                rect=(360, 240, 140, 90),
                on_click=[Action(type="say", speaker="Player", text="There is something here.")],
            )
        )

    def add_spawn(self) -> None:
        scene = self._require_scene()
        self.record_undo()
        number = len(scene.spawns) + 1
        scene.spawns.append(
            SpawnPoint(
                id=self._unique_object_id(scene, "spawn", f"spawn_{number}"),
                position=(160, 390),
                facing="right",
            )
        )

    def add_exit(self) -> None:
        scene = self._require_scene()
        self.record_undo()
        target_scene = self.project.start_scene if self.project else scene.id
        number = len(scene.exits) + 1
        scene.exits.append(
            Exit(
                id=self._unique_object_id(scene, "exit", f"exit_{number}"),
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
        npc_id = self._unique_object_id(scene, "npc", f"npc_{number}")
        scene.npcs.append(
            NPC(
                id=npc_id,
                name=f"NPC {number}",
                sprite=None,
                position=(620, 390),
                lines=["Hello!", "Let's explore."],
                on_click=[Action(type="dialogue", npc=npc_id)],
                dialogue_nodes=[
                    DialogueNode(
                        id="hello",
                        speaker=f"NPC {number}",
                        text="Hello!",
                        choices=[DialogueChoice(text="Goodbye.")],
                    )
                ],
            )
        )

    def add_item_definition(self) -> ItemDefinition:
        if self.project is None:
            raise ValueError("No project is open.")
        self.record_undo()
        number = len(self.project.items) + 1
        item = ItemDefinition(id=f"item_{number}", name=f"Item {number}")
        self.project.items.append(item)
        return item

    def add_scene_item(self, item_id: str | None = None) -> None:
        scene = self._require_scene()
        if self.project is None:
            raise ValueError("No project is open.")
        self.record_undo()
        if not self.project.items:
            self.project.items.append(ItemDefinition(id="item_1", name="Item 1"))
        item_id = item_id or self.project.items[0].id
        number = len(scene.items) + 1
        object_id = self._unique_object_id(scene, "item", f"scene_item_{number}")
        scene.items.append(
            SceneItem(
                id=object_id,
                item_id=item_id,
                rect=(440, 360, 40, 40),
                on_click=[
                    Action(type="give_item", item=item_id),
                    Action(type="set_object_enabled", object_id=object_id, enabled=False),
                ],
            )
        )

    def add_dialogue_node(self, npc_id: str) -> DialogueNode:
        scene = self._require_scene()
        self.record_undo()
        npc = next(item for item in scene.npcs if item.id == npc_id)
        number = len(npc.dialogue_nodes) + 1
        node = DialogueNode(
            id=self._unique_dialogue_node_id(npc, f"node_{number}"),
            speaker=npc.name,
            text="New line.",
        )
        npc.dialogue_nodes.append(node)
        return node

    def duplicate_dialogue_node(self, npc_id: str, node_id: str) -> str:
        npc = self._require_npc(npc_id)
        node = self._require_dialogue_node(npc, node_id)
        self.record_undo()
        duplicate = copy.deepcopy(node)
        duplicate.id = self._unique_dialogue_node_id(npc, f"{node.id}_copy")
        npc.dialogue_nodes.append(duplicate)
        return duplicate.id

    def add_dialogue_choice(self, npc_id: str, node_id: str) -> DialogueChoice:
        npc = self._require_npc(npc_id)
        node = self._require_dialogue_node(npc, node_id)
        self.record_undo()
        choice = DialogueChoice(text="Continue.")
        node.choices.append(choice)
        return choice

    def update_dialogue_choice(
        self,
        npc_id: str,
        node_id: str,
        choice_index: int,
        *,
        text: str | None = None,
        target: str | None = None,
        condition: Condition | None | object = _UNSET,
        actions: list[Action] | None = None,
    ) -> None:
        npc = self._require_npc(npc_id)
        node = self._require_dialogue_node(npc, node_id)
        if choice_index < 0 or choice_index >= len(node.choices):
            raise IndexError(f"Unknown dialogue choice index: {choice_index}")
        choice = copy.deepcopy(node.choices[choice_index])
        if text is not None:
            choice.text = text
        if target is not None:
            choice.target = target or None
        if condition is not _UNSET:
            choice.condition = condition
        if actions is not None:
            choice.actions = actions
        if choice == node.choices[choice_index]:
            return
        self.record_undo()
        node.choices[choice_index] = choice

    def duplicate_dialogue_choice(self, npc_id: str, node_id: str, choice_index: int) -> int:
        npc = self._require_npc(npc_id)
        node = self._require_dialogue_node(npc, node_id)
        if choice_index < 0 or choice_index >= len(node.choices):
            raise IndexError(f"Unknown dialogue choice index: {choice_index}")
        self.record_undo()
        node.choices.insert(choice_index + 1, copy.deepcopy(node.choices[choice_index]))
        return choice_index + 1

    def delete_dialogue_choice(self, npc_id: str, node_id: str, choice_index: int) -> bool:
        npc = self._require_npc(npc_id)
        node = self._require_dialogue_node(npc, node_id)
        if choice_index < 0 or choice_index >= len(node.choices):
            return False
        self.record_undo()
        del node.choices[choice_index]
        return True

    def delete_dialogue_node(self, npc_id: str, node_id: str) -> bool:
        npc = self._require_npc(npc_id)
        for index, node in enumerate(npc.dialogue_nodes):
            if node.id == node_id:
                self.record_undo()
                del npc.dialogue_nodes[index]
                for other in npc.dialogue_nodes:
                    for choice in other.choices:
                        if choice.target == node_id:
                            choice.target = None
                for action in npc.on_click:
                    if action.node == node_id:
                        action.node = npc.dialogue_nodes[0].id if npc.dialogue_nodes else None
                return True
        return False

    def update_dialogue_node(
        self,
        npc_id: str,
        node_id: str,
        *,
        new_id: str | None = None,
        speaker: str | None = None,
        text: str | None = None,
        choices: list[DialogueChoice] | None = None,
        actions: list[Action] | None = None,
    ) -> str:
        npc = self._require_npc(npc_id)
        node = self._require_dialogue_node(npc, node_id)
        changed = False
        if new_id is not None:
            clean_id = self._clean_id(new_id)
            if clean_id != node.id:
                self.record_undo()
                changed = True
                clean_id = self._unique_dialogue_node_id(npc, clean_id)
                old_id = node.id
                node.id = clean_id
                self._retarget_dialogue_node(npc, old_id, clean_id)
        if speaker is not None:
            if node.speaker != speaker:
                if not changed:
                    self.record_undo()
                    changed = True
                node.speaker = speaker
        if text is not None:
            if node.text != text:
                if not changed:
                    self.record_undo()
                    changed = True
                node.text = text
        if choices is not None:
            if node.choices != choices:
                if not changed:
                    self.record_undo()
                    changed = True
                node.choices = choices
        if actions is not None:
            if node.actions != actions:
                if not changed:
                    self.record_undo()
                node.actions = actions
        return node.id

    def set_actions(self, kind: str, object_id: str, actions: list[Action]) -> None:
        scene = self._require_scene()
        collections = {
            "hotspot": scene.hotspots,
            "exit": scene.exits,
            "npc": scene.npcs,
            "item": scene.items,
        }
        for item in collections.get(kind, []):
            if item.id == object_id and hasattr(item, "on_click"):
                if item.on_click == actions:
                    return
                self.record_undo()
                item.on_click = actions
                return
        raise ValueError(f"Unknown action target: {kind}:{object_id}")

    def update_scene_metadata(
        self,
        *,
        scene_id: str | None = None,
        name: str | None = None,
        background: str | None = None,
    ) -> str:
        scene = self._require_scene()
        changed = False
        if scene_id is not None:
            clean_id = self._clean_id(scene_id)
            if clean_id != scene.id:
                self.record_undo()
                changed = True
                if clean_id in self.scenes:
                    clean_id = self._unique_scene_id(clean_id)
                old_id = scene.id
                scene.id = clean_id
                self.scenes[clean_id] = self.scenes.pop(old_id)
                self.current_scene_id = clean_id
                self._replace_scene_path(old_id, clean_id)
                self._retarget_scene_references(old_id, clean_id)
        if name is not None:
            if scene.name != name:
                if not changed:
                    self.record_undo()
                    changed = True
                scene.name = name
        if background is not None:
            if scene.background != background:
                if not changed:
                    self.record_undo()
                scene.background = background
        return scene.id

    def update_scene_object(
        self,
        kind: str,
        object_id: str,
        **fields,
    ) -> str:
        scene = self._require_scene()
        item = self._require_scene_object(scene, kind, object_id)
        original_fields = dict(fields)
        changed = False
        if "id" in fields:
            clean_id = self._clean_id(str(fields.pop("id")))
            if clean_id != item.id:
                self.record_undo()
                changed = True
                clean_id = self._unique_object_id(scene, kind, clean_id)
                old_id = item.id
                item.id = clean_id
                self._retarget_object_references(scene, old_id, clean_id)
        for field_name, value in fields.items():
            if hasattr(item, field_name) and getattr(item, field_name) != value:
                if not changed:
                    self.record_undo()
                    changed = True
                setattr(item, field_name, value)
        if not changed and original_fields:
            return item.id
        return item.id

    def set_layer_state(
        self,
        layer_id: str,
        *,
        visible: bool | None = None,
        locked: bool | None = None,
    ) -> None:
        scene = self._require_scene()
        layer = self._require_layer(scene, layer_id)
        if (visible is None or layer.visible == visible) and (locked is None or layer.locked == locked):
            return
        self.record_undo()
        if visible is not None:
            layer.visible = visible
        if locked is not None:
            layer.locked = locked

    def layer_visible(self, layer_id: str) -> bool:
        scene = self._require_scene()
        layer = next((item for item in scene.layers if item.id == layer_id), None)
        return True if layer is None else layer.visible

    def layer_locked(self, layer_id: str) -> bool:
        scene = self._require_scene()
        layer = next((item for item in scene.layers if item.id == layer_id), None)
        return False if layer is None else layer.locked

    def delete_scene_object(self, kind: str, object_id: str) -> bool:
        scene = self._require_scene()
        collection = self._scene_collection(scene, kind)
        for index, item in enumerate(collection):
            if item.id == object_id:
                self.record_undo()
                del collection[index]
                return True
        return False

    def duplicate_scene_object(self, kind: str, object_id: str) -> str | None:
        scene = self._require_scene()
        collection = self._scene_collection(scene, kind)
        for item in collection:
            if item.id == object_id:
                self.record_undo()
                duplicate = copy.deepcopy(item)
                old_id = duplicate.id
                duplicate.id = self._unique_object_id(scene, kind, f"{old_id}_copy")
                self._offset_duplicate(duplicate)
                self._retarget_duplicate_actions(duplicate, old_id)
                collection.append(duplicate)
                return duplicate.id
        return None

    def duplicate_scene(self, scene_id: str | None = None) -> str:
        if self.project is None:
            raise ValueError("No project is open.")
        source_id = scene_id or self.current_scene_id
        if source_id is None or source_id not in self.scenes:
            raise ValueError(f"Unknown scene: {source_id}")
        self.record_undo()
        source = self.scenes[source_id]
        duplicate = copy.deepcopy(source)
        new_id = self._unique_scene_id(f"{source_id}_copy")
        duplicate.id = new_id
        duplicate.name = f"{source.name} Copy"
        self._retarget_scene_within_duplicate(duplicate, source_id, new_id)
        self.scenes[new_id] = duplicate
        self.project.scenes.append(f"scenes/{new_id}.json")
        self.current_scene_id = new_id
        return new_id

    def delete_scene(self, scene_id: str | None = None) -> bool:
        if self.project is None:
            raise ValueError("No project is open.")
        target_id = scene_id or self.current_scene_id
        if target_id is None or target_id not in self.scenes:
            return False
        if len(self.scenes) <= 1:
            raise ValueError("Cannot delete the only scene.")
        if self.project.start_scene == target_id:
            raise ValueError("Cannot delete the start scene.")
        if self.project.player.default_scene == target_id:
            raise ValueError("Cannot delete the player's default scene.")
        references = self.scene_reference_sources(target_id)
        if references:
            raise ValueError(
                f"Cannot delete scene '{target_id}' while it is referenced by: "
                f"{', '.join(references)}"
            )
        self.record_undo()
        del self.scenes[target_id]
        self.project.scenes = [path for path in self.project.scenes if Path(path).stem != target_id]
        if self.current_scene_id == target_id:
            self.current_scene_id = self.project.start_scene
            if self.current_scene_id not in self.scenes:
                self.current_scene_id = next(iter(self.scenes), None)
        return True

    def scene_reference_sources(self, target_scene_id: str) -> list[str]:
        sources: list[str] = []
        for scene_id, scene in self.scenes.items():
            if scene_id == target_scene_id:
                continue
            for exit_data in scene.exits:
                if exit_data.target_scene == target_scene_id:
                    sources.append(f"{scene_id}:exit:{exit_data.id}")
            for kind, item in self._iter_action_owners(scene):
                if self._actions_reference_scene(getattr(item, "on_click", []), target_scene_id):
                    sources.append(f"{scene_id}:{kind}:{item.id}")
            for npc in scene.npcs:
                for node in npc.dialogue_nodes:
                    if self._actions_reference_scene(node.actions, target_scene_id):
                        sources.append(f"{scene_id}:npc:{npc.id}:dialogue:{node.id}")
                    for index, choice in enumerate(node.choices, start=1):
                        if self._actions_reference_scene(choice.actions, target_scene_id):
                            sources.append(
                                f"{scene_id}:npc:{npc.id}:dialogue:{node.id}:choice:{index}"
                            )
        return sources

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
        if scene.background == relative_path:
            return
        self.record_undo()
        scene.background = relative_path

    def assign_player_sprite(self, relative_path: str) -> None:
        if self.project is None:
            raise ValueError("No project is open.")
        if self.project.player.sprite == relative_path:
            return
        self.record_undo()
        self.project.player.sprite = relative_path

    def assign_npc_sprite(self, npc_id: str, relative_path: str) -> None:
        scene = self._require_scene()
        for npc in scene.npcs:
            if npc.id == npc_id:
                if npc.sprite == relative_path:
                    return
                self.record_undo()
                npc.sprite = relative_path
                return
        raise ValueError(f"Unknown NPC: {npc_id}")

    def set_current_scene_as_start(self) -> None:
        if self.project is None or self.current_scene_id is None:
            raise ValueError("No project is open.")
        if (
            self.project.start_scene == self.current_scene_id
            and self.project.player.default_scene == self.current_scene_id
        ):
            return
        self.record_undo()
        self.project.start_scene = self.current_scene_id
        self.project.player.default_scene = self.current_scene_id

    def snapshot(self) -> ProjectSnapshot | None:
        if self.project is None:
            return None
        return copy.deepcopy(self.project), copy.deepcopy(self.scenes), self.current_scene_id

    def record_snapshot(self, snapshot: ProjectSnapshot | None) -> None:
        if snapshot is None or self.project is None:
            return
        self._undo_stack.append(snapshot)
        self._redo_stack.clear()
        self.is_dirty = True

    def record_undo(self) -> None:
        self.record_snapshot(self.snapshot())

    def undo(self) -> bool:
        if not self._undo_stack or self.project is None:
            return False
        self._redo_stack.append((copy.deepcopy(self.project), copy.deepcopy(self.scenes), self.current_scene_id))
        self.project, self.scenes, self.current_scene_id = self._undo_stack.pop()
        self.is_dirty = True
        return True

    def redo(self) -> bool:
        if not self._redo_stack or self.project is None:
            return False
        self._undo_stack.append((copy.deepcopy(self.project), copy.deepcopy(self.scenes), self.current_scene_id))
        self.project, self.scenes, self.current_scene_id = self._redo_stack.pop()
        self.is_dirty = True
        return True

    def export_playable(self) -> Path:
        if self.project_root is None:
            raise ValueError("No project is open.")
        self.save()
        export_root = self.project_root / "exports" / datetime.now().strftime("playable_%Y-%m-%d_%H%M%S")
        if export_root.exists():
            shutil.rmtree(export_root)
        ignore = shutil.ignore_patterns("autosaves", "exports", "__pycache__")
        shutil.copytree(self.project_root, export_root, ignore=ignore)
        (export_root / "saves").mkdir(exist_ok=True)
        (export_root / "RUN.txt").write_text(
            "Run this project with:\npython -m pce.runtime.main --project .\n",
            encoding="utf-8",
        )
        return export_root

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

    @staticmethod
    def _scene_collection(scene: SceneConfig, kind: str) -> list:
        collections = {
            "hotspot": scene.hotspots,
            "exit": scene.exits,
            "npc": scene.npcs,
            "spawn": scene.spawns,
            "item": scene.items,
        }
        if kind not in collections:
            raise ValueError(f"Unknown scene object kind: {kind}")
        return collections[kind]

    def _require_scene_object(self, scene: SceneConfig, kind: str, object_id: str):
        for item in self._scene_collection(scene, kind):
            if item.id == object_id:
                return item
        raise ValueError(f"Unknown scene object: {kind}:{object_id}")

    def _require_npc(self, npc_id: str) -> NPC:
        scene = self._require_scene()
        for npc in scene.npcs:
            if npc.id == npc_id:
                return npc
        raise ValueError(f"Unknown NPC: {npc_id}")

    @staticmethod
    def _require_dialogue_node(npc: NPC, node_id: str) -> DialogueNode:
        for node in npc.dialogue_nodes:
            if node.id == node_id:
                return node
        raise ValueError(f"Unknown dialogue node: {node_id}")

    @staticmethod
    def _require_layer(scene: SceneConfig, layer_id: str) -> LayerConfig:
        for layer in scene.layers:
            if layer.id == layer_id:
                return layer
        raise ValueError(f"Unknown layer: {layer_id}")

    def _unique_scene_id(self, scene_id: str) -> str:
        base = self._clean_id(scene_id)
        candidate = base
        suffix = 2
        while candidate in self.scenes:
            candidate = f"{base}_{suffix}"
            suffix += 1
        return candidate

    def _unique_object_id(self, scene: SceneConfig, kind: str, object_id: str) -> str:
        existing = {
            item.id
            for collection_kind in ("hotspot", "exit", "npc", "spawn", "item")
            for item in self._scene_collection(scene, collection_kind)
        }
        base = self._clean_id(object_id)
        candidate = base
        if candidate not in existing:
            return candidate
        suffix = 2
        while candidate in existing:
            candidate = f"{base}_{suffix}"
            suffix += 1
        return candidate

    @staticmethod
    def _unique_dialogue_node_id(npc: NPC, node_id: str) -> str:
        existing = {node.id for node in npc.dialogue_nodes}
        base = ProjectController._clean_id(node_id)
        candidate = base
        if candidate not in existing:
            return candidate
        suffix = 2
        while candidate in existing:
            candidate = f"{base}_{suffix}"
            suffix += 1
        return candidate

    @staticmethod
    def _offset_duplicate(item) -> None:
        if hasattr(item, "rect"):
            x, y, width, height = item.rect
            item.rect = (x + 20, y + 20, width, height)
        if hasattr(item, "position"):
            x, y = item.position
            item.position = (x + 20, y)
        if hasattr(item, "walk_path"):
            item.walk_path = [(x + 20, y + 20) for x, y in item.walk_path]

    @staticmethod
    def _retarget_duplicate_actions(item, old_id: str) -> None:
        for action in getattr(item, "on_click", []):
            ProjectController._retarget_duplicate_action(action, old_id, item.id)

    @staticmethod
    def _retarget_duplicate_action(action: Action, old_id: str, new_id: str) -> None:
        if action.npc == old_id:
            action.npc = new_id
        if action.object_id == old_id:
            action.object_id = new_id
        ProjectController._retarget_duplicate_condition(action.condition, old_id, new_id)
        for child in [*action.actions, *action.if_actions, *action.else_actions]:
            ProjectController._retarget_duplicate_action(child, old_id, new_id)

    @staticmethod
    def _retarget_duplicate_condition(condition: Condition | None, old_id: str, new_id: str) -> None:
        if condition is None:
            return
        if condition.object_id == old_id:
            condition.object_id = new_id
        ProjectController._retarget_duplicate_condition(condition.condition, old_id, new_id)

    def _replace_scene_path(self, old_id: str, new_id: str) -> None:
        if self.project is None:
            return
        old_path = f"scenes/{old_id}.json"
        new_path = f"scenes/{new_id}.json"
        self.project.scenes = [new_path if path == old_path else path for path in self.project.scenes]
        if self.project.start_scene == old_id:
            self.project.start_scene = new_id
        if self.project.player.default_scene == old_id:
            self.project.player.default_scene = new_id

    def _retarget_scene_references(self, old_id: str, new_id: str) -> None:
        for scene in self.scenes.values():
            for exit_data in scene.exits:
                if exit_data.target_scene == old_id:
                    exit_data.target_scene = new_id
            for _kind, item in self._iter_action_owners(scene):
                self._retarget_action_scene_refs(getattr(item, "on_click", []), old_id, new_id)
            for npc in scene.npcs:
                for node in npc.dialogue_nodes:
                    self._retarget_action_scene_refs(node.actions, old_id, new_id)
                    for choice in node.choices:
                        self._retarget_action_scene_refs(choice.actions, old_id, new_id)

    def _retarget_object_references(self, scene: SceneConfig, old_id: str, new_id: str) -> None:
        for _kind, item in self._iter_action_owners(scene):
            self._retarget_action_object_refs(getattr(item, "on_click", []), old_id, new_id)
        for npc in scene.npcs:
            if npc.id == new_id:
                for action in npc.on_click:
                    if action.npc == old_id:
                        action.npc = new_id
            for node in npc.dialogue_nodes:
                self._retarget_action_object_refs(node.actions, old_id, new_id)
                for choice in node.choices:
                    self._retarget_action_object_refs(choice.actions, old_id, new_id)

    def _retarget_dialogue_node(self, npc: NPC, old_id: str, new_id: str) -> None:
        for node in npc.dialogue_nodes:
            for choice in node.choices:
                if choice.target == old_id:
                    choice.target = new_id
        for action in npc.on_click:
            if action.node == old_id:
                action.node = new_id

    def _retarget_action_scene_refs(
        self,
        actions: list[Action],
        old_id: str,
        new_id: str,
    ) -> None:
        for action in actions:
            if action.scene == old_id:
                action.scene = new_id
            self._retarget_condition_scene_refs(action.condition, old_id, new_id)
            self._retarget_action_scene_refs(action.actions, old_id, new_id)
            self._retarget_action_scene_refs(action.if_actions, old_id, new_id)
            self._retarget_action_scene_refs(action.else_actions, old_id, new_id)

    def _retarget_action_object_refs(
        self,
        actions: list[Action],
        old_id: str,
        new_id: str,
    ) -> None:
        for action in actions:
            if action.object_id == old_id:
                action.object_id = new_id
            if action.npc == old_id:
                action.npc = new_id
            self._retarget_condition_object_refs(action.condition, old_id, new_id)
            self._retarget_action_object_refs(action.actions, old_id, new_id)
            self._retarget_action_object_refs(action.if_actions, old_id, new_id)
            self._retarget_action_object_refs(action.else_actions, old_id, new_id)

    @staticmethod
    def _iter_action_owners(scene: SceneConfig):
        for item in scene.hotspots:
            yield "hotspot", item
        for item in scene.npcs:
            yield "npc", item
        for item in scene.items:
            yield "item", item

    def _retarget_scene_within_duplicate(
        self,
        scene: SceneConfig,
        old_id: str,
        new_id: str,
    ) -> None:
        for exit_data in scene.exits:
            if exit_data.target_scene == old_id:
                exit_data.target_scene = new_id
        for _kind, item in self._iter_action_owners(scene):
            self._retarget_action_scene_refs(getattr(item, "on_click", []), old_id, new_id)
        for npc in scene.npcs:
            for node in npc.dialogue_nodes:
                self._retarget_action_scene_refs(node.actions, old_id, new_id)
                for choice in node.choices:
                    self._retarget_action_scene_refs(choice.actions, old_id, new_id)

    def _actions_reference_scene(self, actions: list[Action], target_scene_id: str) -> bool:
        for action in actions:
            if action.scene == target_scene_id:
                return True
            if (
                self._actions_reference_scene(action.actions, target_scene_id)
                or self._actions_reference_scene(action.if_actions, target_scene_id)
                or self._actions_reference_scene(action.else_actions, target_scene_id)
            ):
                return True
        return False

    def _retarget_condition_scene_refs(
        self,
        condition: Condition | None,
        old_id: str,
        new_id: str,
    ) -> None:
        # Conditions currently do not store scene ids, but keep traversal centralized
        # for future-compatible nested condition handling.
        if condition is not None and condition.condition is not None:
            self._retarget_condition_scene_refs(condition.condition, old_id, new_id)

    def _retarget_condition_object_refs(
        self,
        condition: Condition | None,
        old_id: str,
        new_id: str,
    ) -> None:
        if condition is None:
            return
        if condition.object_id == old_id:
            condition.object_id = new_id
        self._retarget_condition_object_refs(condition.condition, old_id, new_id)
