Adventure Studio implementation note
===================================

Changed files
-------------

- `src/pce/editor/app.py`
  - Swapped the editor shell to a canvas-first Adventure Studio layout.
  - Wired immediate property, interaction, and dialogue edits through existing controller flows.
  - Added Expert-mode handling and contextual selection summaries.
- `src/pce/editor/project_controller.py`
  - Added `ensure_action()` and `update_action()` to support immediate controller-backed interaction edits with undo safety and no-op guards.
- `src/pce/editor/panels/adventure_shell.py`
  - Added the new shell builder for the toolbar, scene browser, canvas tools, and contextual editor panel.
- `src/pce/editor/panels/properties_panel.py`
  - Reworked visibility rules around the new creator-facing default and Expert disclosure.
- `src/pce/editor/state.py`
  - Added selection summary helpers for contextual titles and subtitles.
- `tests/test_editor_controller.py`
  - Added coverage for immediate action editing helpers and updated visibility expectations for the new contextual workflow.

Manual verification
-------------------

1. Open the editor and load a sample project.
2. Confirm the scene canvas stays visible while selecting the scene, an NPC, a hotspot, an exit, an item, and a spawn from the canvas or outline.
3. Confirm the right-side studio changes with the selection:
   - Scene: scene details and scene-building tools.
   - NPC: placement, quick lines, conversation cards, and responses.
   - Hotspot or item: interaction list and focused action fields.
   - Exit: destination and walk-path fields.
4. Edit visible creator-facing fields and confirm changes apply immediately, mark the project dirty, and can be undone and redone.
5. Turn on Expert mode and confirm IDs, layers, raw conditions, nested actions, and advanced dialogue controls appear without changing the underlying project data shape.
6. Run Validate, Play Scene, and Run Game to confirm the existing playtesting entrypoints still work.
