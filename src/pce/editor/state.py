from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SelectionSummary:
    kind: str | None
    object_id: str | None
    title: str
    subtitle: str


def selection_summary(kind: str | None, object_id: str | None, item) -> SelectionSummary:
    if kind is None or item is None:
        return SelectionSummary(kind, object_id, "Adventure Studio", "Select a scene or object on the canvas.")

    if kind == "scene":
        name = getattr(item, "name", "Scene")
        return SelectionSummary(kind, object_id, name, "Scene overview, layout, and entry setup.")

    display_name = getattr(item, "name", None) or getattr(item, "id", object_id or "Selection")
    subtitles = {
        "hotspot": "Placeable interaction area.",
        "exit": "Scene transition and walk path.",
        "npc": "Character placement, conversation, and interaction.",
        "item": "Collectable or clickable item.",
        "spawn": "Player entry point for this scene.",
    }
    title = f"{display_name}"
    subtitle = subtitles.get(kind, "Selection details.")
    return SelectionSummary(kind, object_id, title, subtitle)
