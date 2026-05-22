from __future__ import annotations

from pce.editor.project_controller import ProjectController


def play_current_scene(controller: ProjectController) -> None:
    controller.save()
    controller.run_runtime(controller.current_scene_id)


def run_full_game(controller: ProjectController) -> None:
    controller.save()
    controller.run_runtime()

