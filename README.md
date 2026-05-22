# PointClick Engine

A first usable build of a Python desktop point-and-click adventure toolkit.

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

Press `F1` for debug overlays. Click hotspots, NPCs, and exits. Exit transitions occur after the player follows the configured path.

## Open the Editor

```powershell
python -m pce.editor.main --project examples/mini_adventure
```

The editor supports creating/opening/saving projects, creating scenes, editing core entities in a simple inspector, validation, autosaves, playtesting the current scene, and running the full game.

