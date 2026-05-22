# PointClick Engine

A creator-ready v2 slice of a Python desktop point-and-click adventure toolkit.

The project has three separated layers:

- `pce.shared`: dataclasses, JSON serialization, asset path helpers, and validation.
- `pce.runtime`: standalone `pygame-ce` runtime for playing project folders.
- `pce.editor`: standalone Dear PyGui editor shell for creating, saving, validating, and playtesting projects.

## Setup

```powershell
python -m pip install -e ".[dev]"
```

## Run Tests

```powershell
python -m pytest
```

## Run the Sample Game

```powershell
python -m pce.runtime.main --project examples/mini_adventure
```

Press `F1` for debug overlays. Click hotspots, NPCs, items, and exits. Exit transitions occur after the player follows the configured path.

Runtime save/load:

```powershell
python -m pce.runtime.main --project examples/mini_adventure --slot quick
```

During play, `S` writes the `quick` save slot and `L` reloads it. Dialogue choices use number keys `1` through `4`.

## Open the Editor

```powershell
python -m pce.editor.main --project examples/mini_adventure
```

The editor supports creating/opening/saving projects, undo/redo, real image-backed canvas previews, scene objects, scene items, basic v2 action editing, validation, autosaves, playtesting the current scene, running the full game, and playable folder export.

## v2 Scope

See `docs/v2_scope.md` for the v2 gap analysis, selected defaults, acceptance checklist, and known exclusions.

