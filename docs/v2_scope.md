# PointClick Engine v2 Scope

v2 turns the first build into a creator-ready vertical slice. The target is a short multi-scene adventure that can be built and tested through the editor without editing JSON.

## PRD Gap Analysis

- v1 runtime can load scenes, move along explicit paths, show subtitles, and transition scenes.
- v1 editor can save basic scene objects, but the canvas is still mostly debug geometry and action editing is raw-field based.
- The PRD defers inventory, save/load, and branching dialogue; v2 intentionally promotes the smallest useful versions of those systems.

## Selected Defaults

- Schema version is `2`; v1 files are rejected with a clear version error.
- Dialogue uses a node-lite list/tree model, not a graph canvas.
- Gameplay save files are named JSON slots in `saves/`.
- Export creates a playable project folder plus launch instructions; it does not package an executable.

## v2 Acceptance Checklist

- Editor canvas renders real backgrounds and sprites with editable overlays.
- Hotspots, exits, NPCs, spawns, scene items, and exit paths can be edited visually.
- Undo/redo works for controller-backed edits.
- Interactions are configured from action/condition/dialogue controls rather than raw JSON.
- Runtime supports variables, inventory, conditionals, one-shot object state, branching dialogue, and named saves.
- Validation detects broken v2 references before playtest.
- Sample project exercises flags, one inventory pickup, branching dialogue, object disabling, save/load, and export.

## Known Exclusions

- No audio, localization, packaging to executable, polygon hotspots, pathfinding, or full dialogue graph canvas.
