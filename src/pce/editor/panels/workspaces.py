from __future__ import annotations

WORKSPACES = ("Build", "Dialogue", "Check")

_WORKSPACE_ALIASES = {
    "studio": "Build",
    "build": "Build",
    "dialogue": "Dialogue",
    "playtest": "Check",
    "check": "Check",
}


def normalize_workspace(workspace: str | None) -> str:
    if workspace is None:
        return "Build"
    return _WORKSPACE_ALIASES.get(workspace.strip().lower(), "Build")


def workspace_panel_visibility(workspace: str | None) -> dict[str, bool]:
    active = normalize_workspace(workspace)
    return {
        "workspace_panel_build": active == "Build",
        "workspace_panel_dialogue": active == "Dialogue",
        "workspace_panel_check": active == "Check",
    }
