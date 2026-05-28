from __future__ import annotations


def build_adventure_toolbar(dpg, app) -> None:
    with dpg.group(horizontal=True):
        dpg.add_text("Adventure Studio")
        dpg.add_spacer(width=18)
        dpg.add_button(label="Open", callback=lambda: dpg.show_item("project_dialog"))
        dpg.add_button(label="Save", callback=lambda: app._save(dpg))
        dpg.add_button(label="Undo", callback=lambda: app._undo(dpg))
        dpg.add_button(label="Redo", callback=lambda: app._redo(dpg))
        dpg.add_button(label="Validate", callback=lambda: app._validate(dpg))
        dpg.add_button(label="Play Scene", callback=lambda: app._play_scene(dpg))
        dpg.add_button(label="Run Game", callback=lambda: app._run_game(dpg))
        dpg.add_spacer(width=18)
        dpg.add_checkbox(
            tag="expert_mode",
            label="Expert",
            default_value=False,
            callback=lambda _s, a: app._set_expert_mode(dpg, a),
        )
        dpg.add_text("", tag="dirty_text")


def build_scene_browser(dpg, app) -> None:
    dpg.add_text("Adventure Outline")
    dpg.add_listbox(
        tag="scene_list",
        items=[],
        num_items=7,
        width=-1,
        callback=lambda _s, a: app._select_scene(dpg, a),
    )
    with dpg.group(horizontal=True):
        dpg.add_input_text(tag="new_scene_id", default_value="scene_2", width=160, hint="scene id")
        dpg.add_button(label="Create", callback=lambda: app._create_scene(dpg))
    with dpg.group(horizontal=True):
        dpg.add_button(label="Duplicate Scene", callback=lambda: app._duplicate_scene(dpg))
        dpg.add_button(label="Delete Scene", callback=lambda: app._request_delete_scene(dpg))
    dpg.add_button(label="Use As Start Scene", callback=lambda: app._set_start_scene(dpg))
    dpg.add_separator()
    dpg.add_text("Story Map")
    with dpg.drawlist(tag="story_map_drawlist", width=1, height=145):
        pass
    dpg.add_listbox(
        tag="story_map_links",
        items=[],
        num_items=5,
        width=-1,
        callback=lambda _s, a: app._select_story_map_link(dpg, a),
    )
    dpg.add_separator()
    dpg.add_text("Objects On Stage")
    dpg.add_listbox(
        tag="object_combo",
        items=[],
        num_items=12,
        width=-1,
        callback=lambda _s, a: app._select_object(dpg, a),
    )


def build_canvas_toolbar(dpg, app) -> None:
    with dpg.group(horizontal=True):
        dpg.add_button(label="Fit", callback=lambda: app._fit_canvas(dpg))
        dpg.add_button(label="-", callback=lambda: app._zoom_canvas(dpg, 0.85))
        dpg.add_button(label="+", callback=lambda: app._zoom_canvas(dpg, 1.15))
        dpg.add_checkbox(
            tag="snap_grid",
            label="Snap",
            default_value=True,
            callback=lambda _s, a: app._set_snap(dpg, a),
        )
        dpg.add_checkbox(
            tag="show_grid",
            label="Grid",
            default_value=True,
            callback=lambda _s, a: app._set_grid(dpg, a),
        )


def build_context_panel(dpg, app) -> None:
    dpg.add_text("Adventure Studio", tag="inspector_title")
    dpg.add_text("Select a scene or object on the canvas.", tag="selection_subtitle", wrap=340)
    dpg.add_text("Pick a scene, hotspot, exit, NPC, item, or spawn to start editing.", tag="context_empty_state", wrap=340)

    with dpg.group(tag="context_scene_tools"):
        dpg.add_text("Scene Building")
        with dpg.group(horizontal=True):
            dpg.add_button(label="Hotspot", callback=lambda: app._add_hotspot(dpg))
            dpg.add_button(label="Exit", callback=lambda: app._add_exit(dpg))
            dpg.add_button(label="NPC", callback=lambda: app._add_npc(dpg))
        with dpg.group(horizontal=True):
            dpg.add_button(label="Spawn", callback=lambda: app._add_spawn(dpg))
            dpg.add_button(label="Item", callback=lambda: app._add_scene_item(dpg))
        dpg.add_button(label="Add Item Definition", callback=lambda: app._add_item_definition(dpg))
        dpg.add_listbox(tag="asset_item_list", items=[], num_items=5, width=-1)
        dpg.add_separator()

    dpg.add_text("Details", tag="context_primary_properties_header")
    with dpg.group(tag="context_primary_properties"):
        dpg.add_input_text(
            tag="prop_name",
            label="Name",
            width=-1,
            callback=lambda _s=None, _a=None: app._apply_properties(dpg),
        )
        dpg.add_input_intx(
            tag="prop_rect",
            label="Bounds",
            size=4,
            width=-1,
            callback=lambda _s=None, _a=None: app._apply_properties(dpg),
        )
        dpg.add_input_intx(
            tag="prop_pos",
            label="Position",
            size=2,
            width=-1,
            callback=lambda _s=None, _a=None: app._apply_properties(dpg),
        )
        dpg.add_input_text(tag="prop_background", label="Background", width=-1, readonly=True)
        dpg.add_button(label="Choose Background...", tag="background_button", callback=lambda: dpg.show_item("background_dialog"))
        dpg.add_input_text(tag="prop_sprite", label="Sprite", width=-1, readonly=True)
        dpg.add_button(label="Choose NPC Sprite...", tag="npc_sprite_button", callback=lambda: dpg.show_item("npc_sprite_dialog"))
        dpg.add_button(label="Choose Player Sprite...", tag="player_sprite_button", callback=lambda: dpg.show_item("player_sprite_dialog"))
        dpg.add_input_text(
            tag="prop_item_id",
            label="Inventory Item",
            width=-1,
            callback=lambda _s=None, _a=None: app._apply_properties(dpg),
        )
        dpg.add_checkbox(
            tag="prop_enabled",
            label="Enabled",
            default_value=True,
            callback=lambda _s=None, _a=None: app._apply_properties(dpg),
        )
        dpg.add_combo(
            tag="prop_facing",
            label="Facing",
            items=["left", "right", "up", "down"],
            width=-1,
            callback=lambda _s=None, _a=None: app._apply_properties(dpg),
        )
        dpg.add_combo(
            tag="prop_target_scene_card",
            label="Destination Scene",
            items=[],
            width=-1,
            callback=lambda _s=None, _a=None: app._apply_exit_destination(dpg),
        )
        dpg.add_combo(
            tag="prop_target_spawn",
            label="Destination Spawn",
            items=[],
            width=-1,
            callback=lambda _s=None, _a=None: app._apply_exit_destination(dpg),
        )
        dpg.add_button(
            label="Preview Exit",
            tag="preview_exit_button",
            callback=lambda: app._preview_selected_exit(dpg),
        )
        dpg.add_text("", tag="exit_warning_text", wrap=340)
        dpg.add_input_text(tag="prop_target_scene", label="Destination Scene Id", width=-1, show=False)
        dpg.add_input_text(
            tag="prop_walk_path",
            label="Walk Path",
            width=-1,
            callback=lambda _s=None, _a=None: app._apply_properties(dpg),
        )
        dpg.add_input_text(
            tag="prop_lines",
            label="Quick Lines",
            width=-1,
            callback=lambda _s=None, _a=None: app._apply_properties(dpg),
        )
        with dpg.group(horizontal=True):
            dpg.add_button(label="Duplicate", tag="duplicate_button", callback=lambda: app._duplicate_selected(dpg))
            dpg.add_button(label="Delete", tag="delete_button", callback=lambda: app._request_delete_selected(dpg))

    dpg.add_separator()
    dpg.add_text("Interaction", tag="context_interactions_header")
    dpg.add_text("Click behavior for the selected hotspot, NPC, or item.", wrap=340, tag="actions_header")
    dpg.add_combo(tag="recipe_template", items=[], width=-1, default_value="Player says...")
    dpg.add_listbox(
        tag="action_list",
        items=[],
        num_items=4,
        width=-1,
        callback=lambda _s, a: app._select_action(dpg, a),
    )
    with dpg.group(horizontal=True, tag="action_buttons"):
        dpg.add_button(label="Add", callback=lambda: app._add_action(dpg))
        dpg.add_button(label="Up", callback=lambda: app._move_action(dpg, -1))
        dpg.add_button(label="Down", callback=lambda: app._move_action(dpg, 1))
        dpg.add_button(label="Duplicate", callback=lambda: app._duplicate_action(dpg))
        dpg.add_button(label="Remove", callback=lambda: app._remove_action(dpg))
    dpg.add_button(
        label="Preview Selected Reaction",
        tag="preview_interaction_button",
        callback=lambda: app._preview_selected_interaction(dpg),
    )
    dpg.add_text("", tag="action_warning_text", wrap=340)
    dpg.add_combo(
        tag="action_type",
        label="Behavior",
        items=[],
        width=-1,
        callback=lambda _s=None, _a=None: app._apply_action(dpg),
    )
    dpg.add_input_text(
        tag="action_speaker",
        label="Speaker",
        width=-1,
        callback=lambda _s=None, _a=None: app._apply_action(dpg),
    )
    dpg.add_input_text(
        tag="action_text",
        label="Line",
        width=-1,
        multiline=True,
        height=70,
        callback=lambda _s=None, _a=None: app._apply_action(dpg),
    )
    dpg.add_combo(tag="action_npc", label="NPC", items=[], width=-1, callback=lambda _s=None, _a=None: app._apply_action(dpg))
    dpg.add_combo(tag="action_node", label="Conversation Card", items=[], width=-1, callback=lambda _s=None, _a=None: app._apply_action(dpg))
    dpg.add_combo(tag="action_scene", label="Scene", items=[], width=-1, callback=lambda _s=None, _a=None: app._apply_action(dpg))
    dpg.add_combo(tag="action_spawn", label="Spawn", items=[], width=-1, callback=lambda _s=None, _a=None: app._apply_action(dpg))
    dpg.add_combo(tag="action_item", label="Item", items=[], width=-1, callback=lambda _s=None, _a=None: app._apply_action(dpg))
    dpg.add_combo(tag="action_object", label="Object", items=[], width=-1, callback=lambda _s=None, _a=None: app._apply_action(dpg))
    dpg.add_input_text(tag="action_variable", label="Variable", width=-1, callback=lambda _s=None, _a=None: app._apply_action(dpg))
    dpg.add_input_text(tag="action_value", label="Value", width=-1, callback=lambda _s=None, _a=None: app._apply_action(dpg))
    dpg.add_checkbox(tag="action_enabled", label="Enabled", default_value=False, callback=lambda _s=None, _a=None: app._apply_action(dpg))

    dpg.add_separator()
    dpg.add_text("Conversation", tag="context_dialogue_header")
    dpg.add_text("Conversation cards and response flow for the selected NPC.", wrap=340, tag="dialogue_header")
    with dpg.group(tag="dialogue_composer"):
        with dpg.group(horizontal=True, tag="dialogue_composer_toolbar"):
            dpg.add_button(label="Add Next Line", tag="dialogue_composer_add_line", callback=lambda: app._composer_add_next_line(dpg))
            dpg.add_button(label="Preview This Conversation", tag="dialogue_composer_preview", callback=lambda: app._preview_conversation(dpg))
        dpg.add_text("", tag="dialogue_composer_validation", wrap=340)
        with dpg.child_window(tag="dialogue_composer_panel", height=320, border=True):
            pass
        dpg.add_text("Branch Overview", tag="dialogue_composer_graph_header")
        with dpg.drawlist(tag="dialogue_graph_overview", width=1, height=180):
            pass
    dpg.add_listbox(
        tag="dialogue_node_list",
        items=[],
        num_items=4,
        width=-1,
        callback=lambda _s, a: app._select_dialogue_node(dpg, a),
    )
    with dpg.group(horizontal=True, tag="dialogue_buttons"):
        dpg.add_button(label="Add Card", callback=lambda: app._add_dialogue_node(dpg))
        dpg.add_button(label="Delete Card", callback=lambda: app._delete_dialogue_node(dpg))
    dpg.add_input_text(
        tag="dialogue_speaker",
        label="Speaker",
        width=-1,
        callback=lambda _s=None, _a=None: app._apply_dialogue_node(dpg),
    )
    dpg.add_input_text(
        tag="dialogue_text",
        label="Line",
        width=-1,
        multiline=True,
        height=80,
        callback=lambda _s=None, _a=None: app._apply_dialogue_node(dpg),
    )
    dpg.add_text("Responses")
    dpg.add_listbox(
        tag="dialogue_choice_list",
        items=[],
        num_items=4,
        width=-1,
        callback=lambda _s, a: app._select_dialogue_choice(dpg, a),
    )
    with dpg.group(horizontal=True, tag="dialogue_choice_buttons"):
        dpg.add_button(label="Add Response", callback=lambda: app._add_dialogue_choice(dpg))
        dpg.add_button(label="Remove Response", callback=lambda: app._remove_dialogue_choice(dpg))
    dpg.add_input_text(
        tag="dialogue_choice_text",
        label="Response Text",
        width=-1,
        callback=lambda _s=None, _a=None: app._apply_dialogue_choice(dpg),
    )
    dpg.add_combo(
        tag="dialogue_choice_target",
        label="Next Card",
        items=[],
        width=-1,
        callback=lambda _s=None, _a=None: app._apply_dialogue_choice(dpg),
    )

    with dpg.tree_node(label="Expert", default_open=False, tag="expert_drawer"):
        dpg.add_text("Advanced fields and raw structures.")
        dpg.add_input_text(tag="prop_id", label="Id", width=-1)
        dpg.add_combo(tag="prop_layer", label="Layer", items=[], width=-1)
        dpg.add_button(label="Apply Details", tag="apply_properties_button", callback=lambda: app._apply_properties(dpg))
        dpg.add_separator()
        dpg.add_text("Advanced Interaction")
        dpg.add_text("Condition", tag="action_condition_header")
        dpg.add_combo(tag="action_condition_type", label="Condition", items=[], width=-1, callback=lambda _s, _a: app._refresh_action_editor(dpg))
        dpg.add_input_text(tag="action_condition_variable", label="Variable", width=-1)
        dpg.add_combo(tag="action_condition_operator", label="Operator", items=[], width=-1)
        dpg.add_input_text(tag="action_condition_value", label="Value", width=-1)
        dpg.add_combo(tag="action_condition_item", label="Item", items=[], width=-1)
        dpg.add_combo(tag="action_condition_object", label="Object", items=[], width=-1)
        dpg.add_combo(tag="action_condition_not_type", label="Not Condition", items=[], width=-1)
        dpg.add_text("Nested Actions", tag="action_actions_header")
        dpg.add_listbox(tag="action_actions_list", items=[], num_items=3, width=-1)
        with dpg.group(horizontal=True, tag="action_actions_buttons"):
            dpg.add_button(label="Add", callback=lambda: app._add_nested_action(dpg, "sequence"))
            dpg.add_button(label="Remove", callback=lambda: app._remove_nested_action(dpg, "sequence"))
        dpg.add_text("If Actions", tag="action_if_actions_header")
        dpg.add_listbox(tag="action_if_actions_list", items=[], num_items=3, width=-1)
        with dpg.group(horizontal=True, tag="action_if_actions_buttons"):
            dpg.add_button(label="Add", callback=lambda: app._add_nested_action(dpg, "if"))
            dpg.add_button(label="Remove", callback=lambda: app._remove_nested_action(dpg, "if"))
        dpg.add_text("Else Actions", tag="action_else_actions_header")
        dpg.add_listbox(tag="action_else_actions_list", items=[], num_items=3, width=-1)
        with dpg.group(horizontal=True, tag="action_else_actions_buttons"):
            dpg.add_button(label="Add", callback=lambda: app._add_nested_action(dpg, "else"))
            dpg.add_button(label="Remove", callback=lambda: app._remove_nested_action(dpg, "else"))
        dpg.add_input_text(tag="action_condition_json", label="Condition JSON", width=-1, multiline=True, height=70, show=False)
        dpg.add_input_text(tag="action_actions_json", label="Nested Actions JSON", width=-1, multiline=True, height=90, show=False)
        dpg.add_input_text(tag="action_if_actions_json", label="If Actions JSON", width=-1, multiline=True, height=90, show=False)
        dpg.add_input_text(tag="action_else_actions_json", label="Else Actions JSON", width=-1, multiline=True, height=90, show=False)
        dpg.add_button(label="Apply Interaction", tag="apply_action_button", callback=lambda: app._apply_action(dpg))
        dpg.add_separator()
        dpg.add_text("Advanced Conversation")
        dpg.add_input_text(tag="dialogue_node_id", label="Card Id", width=-1)
        dpg.add_text("Card Actions", tag="dialogue_node_actions_header")
        dpg.add_listbox(tag="dialogue_node_action_list", items=[], num_items=3, width=-1)
        with dpg.group(horizontal=True, tag="dialogue_node_action_buttons"):
            dpg.add_button(label="Add", callback=lambda: app._add_dialogue_node_action(dpg))
            dpg.add_button(label="Remove", callback=lambda: app._remove_dialogue_node_action(dpg))
        dpg.add_input_text(tag="dialogue_node_actions_json", label="Card Actions JSON", width=-1, multiline=True, height=72, show=False)
        dpg.add_button(label="Apply Card", tag="apply_dialogue_node_button", callback=lambda: app._apply_dialogue_node(dpg))
        dpg.add_text("Choice Condition", tag="dialogue_choice_condition_header")
        dpg.add_combo(tag="dialogue_choice_condition_type", label="Condition", items=[], width=-1, callback=lambda _s, _a: app._refresh_dialogue_choice_condition_editor(dpg))
        dpg.add_input_text(tag="dialogue_choice_condition_variable", label="Variable", width=-1)
        dpg.add_combo(tag="dialogue_choice_condition_operator", label="Operator", items=[], width=-1)
        dpg.add_input_text(tag="dialogue_choice_condition_value", label="Value", width=-1)
        dpg.add_combo(tag="dialogue_choice_condition_item", label="Item", items=[], width=-1)
        dpg.add_combo(tag="dialogue_choice_condition_object", label="Object", items=[], width=-1)
        dpg.add_combo(tag="dialogue_choice_condition_not_type", label="Not Condition", items=[], width=-1)
        dpg.add_text("Choice Actions", tag="dialogue_choice_actions_header")
        dpg.add_listbox(tag="dialogue_choice_action_list", items=[], num_items=3, width=-1)
        with dpg.group(horizontal=True, tag="dialogue_choice_action_buttons"):
            dpg.add_button(label="Add", callback=lambda: app._add_dialogue_choice_action(dpg))
            dpg.add_button(label="Remove", callback=lambda: app._remove_dialogue_choice_action(dpg))
        dpg.add_input_text(tag="dialogue_choice_condition_json", label="Choice Condition JSON", width=-1, multiline=True, height=70, show=False)
        dpg.add_input_text(tag="dialogue_choice_actions_json", label="Choice Actions JSON", width=-1, multiline=True, height=90, show=False)
        dpg.add_button(label="Apply Response", tag="apply_choice_button", callback=lambda: app._apply_dialogue_choice(dpg))
