from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from pce.runtime.dialogue import DialogueSystem, RuntimeChoice
from pce.runtime.player import Player
from pce.runtime.scene_manager import SceneManager
from pce.runtime.state import evaluate_condition, object_key
from pce.shared.models import Action, ProjectConfig, RuntimeState, SceneConfig


@dataclass(slots=True)
class RuntimeContext:
    project: ProjectConfig
    scene_manager: SceneManager
    player: Player
    dialogue: DialogueSystem
    state: RuntimeState

    @property
    def current_scene(self) -> SceneConfig:
        return self.scene_manager.current_scene


class ActionRunner:
    def __init__(self, context: RuntimeContext) -> None:
        self.context = context
        self.pending: deque[Action] = deque()
        self.waiting_for_movement = False

    @property
    def active(self) -> bool:
        return bool(self.pending) or self.waiting_for_movement

    def start(self, actions: list[Action]) -> None:
        self.pending.extend(actions)
        self._step()

    def update(self) -> None:
        if self.waiting_for_movement and not self.context.player.moving:
            self.waiting_for_movement = False
            self._step()
        elif not self.context.dialogue.active:
            self._step()

    def _step(self) -> None:
        while self.pending and not self.context.dialogue.active and not self.context.player.moving:
            action = self.pending.popleft()
            if action.type == "say":
                self.context.dialogue.say(action.speaker or "", action.text or "")
                return
            if action.type == "dialogue":
                npc = next((item for item in self.context.current_scene.npcs if item.id == action.npc), None)
                if npc is not None:
                    node_id = action.node
                    node = next((item for item in npc.dialogue_nodes if item.id == node_id), None)
                    if node is not None:
                        choices = [
                            RuntimeChoice(choice.text, choice.target, choice.actions)
                            for choice in node.choices
                            if evaluate_condition(
                                self.context.state,
                                choice.condition,
                                self.context.scene_manager.current_scene_id,
                            )
                        ]
                        self.context.dialogue.show_node(node.speaker or npc.name, node.text, choices)
                    else:
                        self.context.dialogue.start_lines(npc.name, npc.lines)
                return
            if action.type == "move_player":
                self.context.player.move_along(action.path)
                self.waiting_for_movement = bool(action.path)
                return
            if action.type == "change_scene":
                if action.scene and action.spawn:
                    self.context.player.position = self.context.scene_manager.change_scene(
                        action.scene,
                        action.spawn,
                    )
                    self.context.player._precise_x = float(self.context.player.position[0])
                    self.context.player._precise_y = float(self.context.player.position[1])
                    self.context.state.current_scene = self.context.scene_manager.current_scene_id
                    self.context.state.player_position = self.context.player.position
                continue
            if action.type == "sequence":
                self.pending.extendleft(reversed(action.actions))
            if action.type == "set_variable" and action.variable:
                self.context.state.variables[action.variable] = action.value
                continue
            if action.type == "give_item" and action.item:
                if action.item not in self.context.state.inventory:
                    self.context.state.inventory.append(action.item)
                continue
            if action.type == "remove_item" and action.item:
                if action.item in self.context.state.inventory:
                    self.context.state.inventory.remove(action.item)
                continue
            if action.type == "set_object_enabled" and action.object_id:
                key = object_key(self.context.scene_manager.current_scene_id, action.object_id)
                self.context.state.object_enabled[key] = bool(action.enabled)
                continue
            if action.type == "conditional":
                selected = action.if_actions
                if not evaluate_condition(
                    self.context.state,
                    action.condition,
                    self.context.scene_manager.current_scene_id,
                ):
                    selected = action.else_actions
                self.pending.extendleft(reversed(selected))

