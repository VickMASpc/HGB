# PointClick Engine

PointClick Engine is a Python toolkit for building small 2D point-and-click adventure games with a desktop editor and a standalone runtime.

This repository currently focuses on a creator-ready `v2` vertical slice:

- A Dear PyGui editor for building scenes, placing objects, editing interactions, authoring branching dialogue, validating projects, and launching playtests.
- A `pygame-ce` runtime that loads portable project folders and runs them as playable adventures.
- Shared schema, serialization, and validation code used by both the editor and the runtime.

The included sample project, `examples/mini_adventure`, demonstrates the intended workflow end to end.

## What You Can Build

The current feature set supports:

- Multiple scenes with named spawn points
- Clickable hotspots
- Scene exits with explicit walk paths
- NPCs with sprites, quick lines, and branching dialogue
- Scene items that grant inventory items or toggle world state
- Variables, inventory checks, object enabled checks, and conditional actions
- Save/load slots during runtime
- Validation for broken references and common authoring mistakes
- Export to a portable playable folder

This version does not aim to be a full commercial adventure framework yet. It is a focused vertical slice meant to support short games and editor-driven iteration.

## Project Structure

The codebase is split into three main packages:

- `src/pce/shared`
  Shared dataclasses, schema conversion, serialization helpers, constants, asset path helpers, and project validation.

- `src/pce/runtime`
  The playable game runtime built on `pygame-ce`.

- `src/pce/editor`
  The visual editor built on Dear PyGui.

Important top-level folders:

- `examples/mini_adventure`
  Reference project showing the expected project format and gameplay features.

- `tests`
  Automated coverage for loading, validation, runtime behavior, and editor/controller operations.

- `docs`
  Supporting notes for scope and editor implementation direction.

## Requirements

- Python `3.11+`
- A desktop environment capable of opening native windows

The project depends on:

- `pygame-ce`
- `dearpygui`

Developer extras include:

- `pytest`
- `ruff`

## Installation

Install the project in editable mode with developer tools:

```powershell
python -m pip install -e ".[dev]"
```

You can also use the console scripts after installation:

```powershell
pce-editor --project examples/mini_adventure
pce-runtime --project examples/mini_adventure
```

## Quick Start

### Open the sample project in the editor

```powershell
python -m pce.editor.main --project examples/mini_adventure
```

### Run the sample project

```powershell
python -m pce.runtime.main --project examples/mini_adventure
```

### Run tests

```powershell
python -m pytest
```

## Editor Overview

The editor is built around a canvas-first layout:

- Left panel: project and scene outline
- Center panel: visual scene canvas
- Right panel: contextual editing controls for the current selection
- Bottom area: status and validation feedback

The editor supports:

- Creating and opening projects
- Saving and autosaving
- Undo and redo
- Visual placement and resizing of scene objects
- Immediate editing of most creator-facing fields
- Validation before playtest
- Current-scene playtest and full-game playtest
- Playable export

### Main Toolbar

The top toolbar exposes:

- Open
- Save
- Undo
- Redo
- Validate
- Play Scene
- Run Game
- Expert mode toggle

### Scene Authoring

When the scene itself is selected, the editor exposes scene-building controls for:

- Hotspots
- Exits
- NPCs
- Spawn points
- Scene items
- Item definitions

You can also assign the current scene as the project start scene.

### Object Editing

Depending on the selected object, the editor shows creator-facing controls such as:

- Name
- Position
- Bounds
- Background
- Sprite
- Inventory item binding
- Enabled state
- Exit destination scene
- Exit destination spawn
- Exit walk path
- NPC quick lines

Most of these update immediately and participate in undo/redo.

### Interaction Editing

Hotspots, NPCs, and scene items can define `on_click` behavior using actions such as:

- `say`
- `dialogue`
- `move_player`
- `change_scene`
- `sequence`
- `set_variable`
- `give_item`
- `remove_item`
- `set_object_enabled`
- `conditional`

In normal mode, the editor favors direct editing. In Expert mode, additional low-level controls appear for conditions, nested actions, and implementation details.

### Dialogue Composer

Selecting an NPC exposes a screenplay-style conversation composer.

The composer is designed around readable dialogue flow instead of form-heavy cards:

- NPC lines are shown as conversation beats
- Player replies appear indented beneath each line
- Dialogue text can be edited inline
- Replies can be added, duplicated, reordered, and deleted
- Reply destinations are chosen with plain-language options:
  - `Continue`
  - `End conversation`
  - `New branch`
- Node IDs and wiring stay automatic and hidden in normal use
- Optional condition/effect chips summarize extra behavior, for example:
  - `Requires: clubhouse_key`
  - `Gives: map`
  - `Sets: dog_ready`

Expert mode keeps the deeper controls available:

- Manual node ids
- Detailed conditions
- Detailed reply effects
- Advanced action editing

### Playtesting From the Editor

The editor provides two runtime entry points:

- `Play Scene`
  Saves the project and launches the current scene.

- `Run Game`
  Saves the project and launches the full project from its configured starting point.

For conversation work, the composer also includes `Preview This Conversation`, which saves first and launches the current-scene playtest so the selected NPC can be tested immediately.

### Export

Export creates a playable copy of the project under an `exports/` folder inside the project root.

The export:

- Saves the current project first
- Copies the portable project data
- Creates a `saves/` folder
- Writes a `RUN.txt` file with launch instructions

It does not currently package a standalone executable.

## Runtime Overview

The runtime loads a project folder and runs it directly.

Basic command:

```powershell
python -m pce.runtime.main --project examples/mini_adventure
```

Optional arguments:

```powershell
python -m pce.runtime.main --project examples/mini_adventure --scene town_square
python -m pce.runtime.main --project examples/mini_adventure --slot quick
```

- `--scene`
  Overrides the initial scene for testing.

- `--slot`
  Loads an existing named save slot on startup.

### Runtime Controls

- Mouse click: interact with hotspots, NPCs, items, and exits
- `1` to `4`: choose dialogue responses
- `S`: save to the `quick` slot
- `L`: load the `quick` slot
- `F1`: toggle debug overlay
- `Esc`: quit

### Runtime Behavior

The runtime supports:

- Walking along authored paths
- Scene transitions
- Subtitles and dialogue choices
- Inventory-backed conditions
- Variable-backed conditions
- Object enabled/disabled state
- Action sequencing
- Conditional actions
- Named save slots stored as JSON

## Validation

Validation is shared between the editor and the runtime-facing project format.

It checks for issues such as:

- Missing `game.json`
- Invalid schema version
- Missing scene files
- Scene id mismatches
- Missing start scene
- Missing background or sprite assets
- Duplicate scene object ids
- Invalid rectangles
- Exits without walk paths
- Missing action references
- Missing condition references
- Empty dialogue lines
- Missing dialogue targets
- Unreachable dialogue branches

In the editor, validation results are shown in the UI. In code, validation lives in [src/pce/shared/validation.py](C:/Users/VictorMonteiroDeArau/Downloads/HGP/HGB/HGB/src/pce/shared/validation.py).

## Project Format

Projects are portable folders rooted by `game.json`.

A typical layout looks like this:

```text
my_project/
  game.json
  assets/
    backgrounds/
    sprites/
    ui/
  scenes/
    town_square.json
    clubhouse.json
  saves/
```

### `game.json`

The root project file defines:

- `schema_version`
- `title`
- `start_scene`
- `resolution`
- `player`
- `scenes`
- `items`

Example fields from the sample project:

- `start_scene: "town_square"`
- `player.default_scene: "town_square"`
- `player.default_spawn: "start"`

### Scene Files

Each scene file contains:

- `id`
- `name`
- `background`
- `layers`
- `spawns`
- `hotspots`
- `exits`
- `npcs`
- `items`

### Dialogue Model

Dialogue uses the existing node-and-choice schema:

- `DialogueNode`
  - `id`
  - `speaker`
  - `text`
  - `choices`
  - `actions`

- `DialogueChoice`
  - `text`
  - `target`
  - `actions`
  - `condition`

The runtime semantics are intentionally simple:

- A node shows one spoken line
- Choices are displayed to the player
- Choosing a reply can run actions
- A choice can point to another node or end the conversation

### Actions and Conditions

Important shared models live in [src/pce/shared/models.py](C:/Users/VictorMonteiroDeArau/Downloads/HGP/HGB/HGB/src/pce/shared/models.py).

Supported condition types:

- `always`
- `variable`
- `has_item`
- `object_enabled`
- `not`

Supported action types:

- `say`
- `dialogue`
- `move_player`
- `change_scene`
- `sequence`
- `set_variable`
- `give_item`
- `remove_item`
- `set_object_enabled`
- `conditional`

## Sample Project

The sample game in `examples/mini_adventure` demonstrates:

- Multiple scenes
- An inventory pickup
- A branching NPC conversation
- Dialogue conditions based on inventory
- Variable-setting effects
- Object disabling after pickup
- Scene transitions

It is the best starting point for understanding the expected data shape and editor workflow.

## Tests and Quality

Run the full automated test suite with:

```powershell
python -m pytest
```

Coverage includes:

- Project loading
- Scene loading
- Runtime state behavior
- Action execution
- Validation
- Editor/controller mutations
- Dialogue retargeting
- Undo/redo

Linting is available with:

```powershell
python -m ruff check .
```

## Documentation Notes

Additional project notes live in:

- [docs/v2_scope.md](C:/Users/VictorMonteiroDeArau/Downloads/HGP/HGB/HGB/docs/v2_scope.md)
- [docs/adventure_studio_implementation_note.md](C:/Users/VictorMonteiroDeArau/Downloads/HGP/HGB/HGB/docs/adventure_studio_implementation_note.md)

## Current Scope and Limitations

This repository intentionally excludes several larger systems for now:

- Audio
- Localization
- Executable packaging
- Polygon hotspots
- Pathfinding
- A full graph-canvas dialogue editor

The current editor aims to make short adventure production practical without requiring direct JSON editing.
