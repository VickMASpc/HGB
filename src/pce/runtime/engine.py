from __future__ import annotations

from pathlib import Path

from pce.runtime.actions import ActionRunner, RuntimeContext
from pce.runtime.debug_overlay import DebugOverlayState
from pce.runtime.dialogue import DialogueSystem
from pce.runtime.player import Player
from pce.runtime.renderer import Renderer
from pce.runtime.scene_manager import SceneManager
from pce.runtime.scene_runtime import SceneRuntime
from pce.runtime.state import load_state, load_state_if_exists, save_state
from pce.shared.models import RuntimeState
from pce.shared.serialization import load_project, load_scenes
from pce.shared.validation import has_errors, validate_project


class Engine:
    def __init__(
        self,
        project_root: Path,
        start_scene: str | None = None,
        slot: str | None = None,
    ) -> None:
        self.project_root = project_root
        self.project = load_project(project_root)
        self.scenes = load_scenes(project_root, self.project)
        issues = validate_project(project_root, self.project, self.scenes)
        if has_errors(issues):
            formatted = "\n".join(f"{issue.code}: {issue.message}" for issue in issues)
            raise ValueError(f"Project validation failed:\n{formatted}")
        loaded_state = load_state_if_exists(project_root, slot) if slot else None
        self.scene_manager = SceneManager(
            self.project,
            self.scenes,
            loaded_state.current_scene if loaded_state else start_scene,
        )
        self.player = Player(loaded_state.player_position if loaded_state else self.scene_manager.spawn_position())
        self.dialogue = DialogueSystem()
        self.state = loaded_state or RuntimeState(
            current_scene=self.scene_manager.current_scene_id,
            player_position=self.player.position,
        )
        self.actions = ActionRunner(
            RuntimeContext(self.project, self.scene_manager, self.player, self.dialogue, self.state)
        )
        self.debug = DebugOverlayState()
        self.running = True

    def handle_click(self, position: tuple[int, int]) -> None:
        if self.dialogue.active:
            self.dialogue.advance()
            return
        if self.actions.active or self.player.moving:
            return
        target = SceneRuntime(self.scene_manager.current_scene, self.state).hit_test(position)
        if target is not None:
            self.actions.start(target.actions)

    def choose_dialogue(self, index: int) -> None:
        choice = self.dialogue.choose(index)
        if choice is None:
            return
        if choice.target:
            npc = next(
                (
                    item
                    for item in self.scene_manager.current_scene.npcs
                    if any(node.id == choice.target for node in item.dialogue_nodes)
                ),
                None,
            )
            if npc is not None:
                self.actions.start([*choice.actions, *[self._dialogue_action(npc.id, choice.target)]])
                return
        self.actions.start(choice.actions)

    def update(self, dt: float) -> None:
        self.player.update(dt)
        self.state.player_position = self.player.position
        self.actions.update()

    def save_slot(self, slot: str) -> Path:
        self.state.current_scene = self.scene_manager.current_scene_id
        self.state.player_position = self.player.position
        return save_state(self.project_root, slot, self.state)

    def load_slot(self, slot: str) -> None:
        self.state = load_state(self.project_root, slot)
        self.scene_manager.current_scene_id = self.state.current_scene
        self.player.position = self.state.player_position
        self.player._precise_x = float(self.player.position[0])
        self.player._precise_y = float(self.player.position[1])
        self.actions.context.state = self.state

    @staticmethod
    def _dialogue_action(npc_id: str, node_id: str):
        from pce.shared.models import Action

        return Action(type="dialogue", npc=npc_id, node=node_id)


class PygameApp:
    def __init__(
        self,
        project_root: Path,
        start_scene: str | None = None,
        slot: str | None = None,
    ) -> None:
        import pygame

        pygame.init()
        self.pygame = pygame
        self.engine = Engine(project_root, start_scene, slot)
        self.renderer = Renderer(project_root, self.engine.project)
        self.clock = pygame.time.Clock()

    def run(self) -> None:
        pygame = self.pygame
        while self.engine.running:
            dt = self.clock.tick(60) / 1000.0
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.engine.running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.engine.running = False
                    elif event.key == pygame.K_F1:
                        self.engine.debug.toggle()
                    elif event.key == pygame.K_s:
                        self.engine.save_slot("quick")
                    elif event.key == pygame.K_l:
                        self.engine.load_slot("quick")
                    elif pygame.K_1 <= event.key <= pygame.K_4:
                        self.engine.choose_dialogue(event.key - pygame.K_1)
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    self.engine.handle_click(event.pos)
            self.engine.update(dt)
            current_subtitle = self.engine.dialogue.current
            subtitle = None
            if current_subtitle is not None:
                subtitle = (current_subtitle.speaker, current_subtitle.text)
            self.renderer.draw(
                self.engine.scene_manager.current_scene,
                self.engine.player.position,
                subtitle,
                [choice.text for choice in self.engine.dialogue.choices],
                self.engine.state.inventory,
                self.engine.debug.enabled,
            )
        pygame.quit()

