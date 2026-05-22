from __future__ import annotations

from pathlib import Path

from pce.runtime.scene_runtime import npc_rect
from pce.shared.models import ProjectConfig, SceneConfig


class Renderer:
    def __init__(self, project_root: Path, project: ProjectConfig) -> None:
        import pygame

        self.pygame = pygame
        self.project_root = project_root
        self.screen = pygame.display.set_mode((project.resolution.width, project.resolution.height))
        pygame.display.set_caption(project.title)
        self.font = pygame.font.Font(None, 28)
        self.small_font = pygame.font.Font(None, 20)
        self.backgrounds: dict[str, object] = {}
        self.player_sprite = self._load_image(project.player.sprite, (48, 72))

    def _load_image(self, relative_path: str | None, fallback_size: tuple[int, int]) -> object | None:
        if not relative_path:
            return None
        path = self.project_root / relative_path
        if not path.exists():
            return None
        try:
            image = self.pygame.image.load(str(path)).convert_alpha()
            return image
        except Exception:
            return None

    def draw(
        self,
        scene: SceneConfig,
        player_position: tuple[int, int],
        subtitle: tuple[str, str] | None,
        debug: bool,
    ) -> None:
        pygame = self.pygame
        background = self.backgrounds.get(scene.id)
        if background is None:
            background = self._load_image(scene.background, self.screen.get_size())
            self.backgrounds[scene.id] = background
        if background is not None:
            self.screen.blit(background, (0, 0))
        else:
            self.screen.fill((30, 34, 42))

        for npc in scene.npcs:
            rect = npc_rect(npc)
            image = self._load_image(npc.sprite, (48, 72))
            if image:
                self.screen.blit(image, (rect[0], rect[1]))
            else:
                pygame.draw.rect(self.screen, (140, 92, 172), rect, border_radius=4)

        px, py = player_position
        if self.player_sprite:
            self.screen.blit(self.player_sprite, (px - 24, py - 72))
        else:
            pygame.draw.rect(self.screen, (45, 88, 168), (px - 20, py - 70, 40, 70), border_radius=4)

        if debug:
            self._draw_debug(scene)
        if subtitle:
            self._draw_subtitle(*subtitle)
        pygame.display.flip()

    def _draw_debug(self, scene: SceneConfig) -> None:
        pygame = self.pygame
        for hotspot in scene.hotspots:
            pygame.draw.rect(self.screen, (255, 212, 96), hotspot.rect, 2)
            self._label(hotspot.id, (hotspot.rect[0], hotspot.rect[1] - 18), (255, 212, 96))
        for exit_data in scene.exits:
            pygame.draw.rect(self.screen, (95, 196, 134), exit_data.rect, 2)
            self._label(exit_data.id, (exit_data.rect[0], exit_data.rect[1] - 18), (95, 196, 134))
            if len(exit_data.walk_path) > 1:
                pygame.draw.lines(self.screen, (95, 196, 134), False, exit_data.walk_path, 3)
            for point in exit_data.walk_path:
                pygame.draw.circle(self.screen, (95, 196, 134), point, 5)

    def _label(self, text: str, position: tuple[int, int], color: tuple[int, int, int]) -> None:
        surface = self.small_font.render(text, True, color)
        self.screen.blit(surface, position)

    def _draw_subtitle(self, speaker: str, text: str) -> None:
        pygame = self.pygame
        width, height = self.screen.get_size()
        box = pygame.Rect(80, height - 125, width - 160, 82)
        pygame.draw.rect(self.screen, (12, 14, 18), box, border_radius=8)
        pygame.draw.rect(self.screen, (235, 235, 235), box, 2, border_radius=8)
        speaker_surface = self.small_font.render(speaker, True, (164, 210, 255))
        text_surface = self.font.render(text, True, (250, 250, 250))
        self.screen.blit(speaker_surface, (box.x + 18, box.y + 12))
        self.screen.blit(text_surface, (box.x + 18, box.y + 36))

