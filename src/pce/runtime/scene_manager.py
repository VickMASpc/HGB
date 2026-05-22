from __future__ import annotations

from pce.shared.models import Point, ProjectConfig, SceneConfig


class SceneManager:
    def __init__(
        self,
        project: ProjectConfig,
        scenes: dict[str, SceneConfig],
        start_scene: str | None = None,
    ) -> None:
        self.project = project
        self.scenes = scenes
        self.current_scene_id = start_scene or project.start_scene
        if self.current_scene_id not in scenes:
            raise ValueError(f"Unknown start scene: {self.current_scene_id}")

    @property
    def current_scene(self) -> SceneConfig:
        return self.scenes[self.current_scene_id]

    def spawn_position(self, spawn_id: str | None = None) -> Point:
        selected_spawn = spawn_id or self.project.player.default_spawn
        for spawn in self.current_scene.spawns:
            if spawn.id == selected_spawn:
                return spawn.position
        if self.current_scene.spawns:
            return self.current_scene.spawns[0].position
        raise ValueError(f"Scene '{self.current_scene_id}' has no spawn points.")

    def change_scene(self, scene_id: str, spawn_id: str) -> Point:
        if scene_id not in self.scenes:
            raise ValueError(f"Unknown target scene: {scene_id}")
        self.current_scene_id = scene_id
        return self.spawn_position(spawn_id)

