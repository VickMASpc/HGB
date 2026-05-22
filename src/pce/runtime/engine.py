from __future__ import annotations

from pathlib import Path

from pce.runtime.actions import ActionRunner, RuntimeContext
from pce.runtime.debug_overlay import DebugOverlayState
from pce.runtime.dialogue import DialogueSystem
from pce.runtime.player import Player
from pce.runtime.renderer import Renderer
from pce.runtime.scene_manager import SceneManager
from pce.runtime.scene_runtime import SceneRuntime
from pce.shared.serialization import load_project, load_scenes
from pce.shared.validation import has_errors, validate_project


class Engine:
    def __init__(self, project_root: Path, start_scene: str | None = None) -> None:
        self.project_root = project_root
        self.project = load_project(project_root)
        self.scenes = load_scenes(project_root, self.project)
        issues = validate_project(project_root, self.project, self.scenes)
        if has_errors(issues):
            formatted = "\n".join(f"{issue.code}: {issue.message}" for issue in issues)
            raise ValueError(f"Project validation failed:\n{formatted}")
        self.scene_manager = SceneManager(self.project, self.scenes, start_scene)
        self.player = Player(self.scene_manager.spawn_position())
        self.dialogue = DialogueSystem()
        self.actions = ActionRunner(RuntimeContext(self.scene_manager, self.player, self.dialogue))
        self.debug = DebugOverlayState()
        self.running = True

    def handle_click(self, position: tuple[int, int]) -> None:
        if self.dialogue.active:
            self.dialogue.advance()
            return
        if self.actions.active or self.player.moving:
            return
        target = SceneRuntime(self.scene_manager.current_scene).hit_test(position)
        if target is not None:
            self.actions.start(target.actions)

    def update(self, dt: float) -> None:
        self.player.update(dt)
        self.actions.update()


class PygameApp:
    def __init__(self, project_root: Path, start_scene: str | None = None) -> None:
        import pygame

        pygame.init()
        self.pygame = pygame
        self.engine = Engine(project_root, start_scene)
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
                self.engine.debug.enabled,
            )
        pygame.quit()

