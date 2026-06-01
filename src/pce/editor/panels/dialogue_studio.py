from __future__ import annotations

from dataclasses import dataclass

from pce.editor.panels.action_list_panel import ACTION_TYPES
from pce.editor.panels.visual_editors import CONDITION_OPERATORS, CONDITION_TYPES, action_label
from pce.shared.models import Action, Condition, DialogueChoice, NPC

DESTINATION_OPTIONS = ["Continue", "End conversation", "New branch"]


@dataclass(frozen=True, slots=True)
class DialogueValidationIssue:
    code: str
    message: str
    node_id: str | None = None
    choice_index: int | None = None


def node_card_title(npc: NPC, node_id: str, *, simple: bool = True) -> str:
    for index, node in enumerate(npc.dialogue_nodes, start=1):
        if node.id == node_id:
            text = node.text.strip().replace("\n", " ")
            preview = text[:42] + "..." if len(text) > 42 else text
            title = f"Card {index}"
            if preview:
                title = f"{title}: {preview}"
            if not simple:
                title = f"{title} ({node.id})"
            return title
    return "End conversation" if not node_id else f"Missing: {node_id}"


def target_options(npc: NPC, *, simple: bool = True) -> list[str]:
    return ["End conversation", *(node_card_title(npc, node.id, simple=simple) for node in npc.dialogue_nodes)]


def target_label(npc: NPC, target: str | None, *, simple: bool = True) -> str:
    if not target:
        return "End conversation"
    return node_card_title(npc, target, simple=simple)


def target_id_from_label(npc: NPC, label: str) -> str | None:
    if label == "End conversation":
        return None
    for node in npc.dialogue_nodes:
        if label in {
            node_card_title(npc, node.id, simple=True),
            node_card_title(npc, node.id, simple=False),
            node.id,
        }:
            return node.id
    return None


def next_node_id(npc: NPC, node_id: str) -> str | None:
    for index, node in enumerate(npc.dialogue_nodes):
        if node.id == node_id and index + 1 < len(npc.dialogue_nodes):
            return npc.dialogue_nodes[index + 1].id
    return None


def destination_label(npc: NPC, node_id: str, choice: DialogueChoice) -> str:
    next_id = next_node_id(npc, node_id)
    if choice.target is None:
        return "End conversation"
    if next_id is not None and choice.target == next_id:
        return "Continue"
    return "New branch"


def condition_label(condition: Condition | None) -> str:
    if condition is None or condition.type == "always":
        return "Always available"
    if condition.type == "variable":
        return f"When {condition.variable or 'variable'} {condition.operator} {condition.value!r}"
    if condition.type == "has_item":
        return f"Requires item: {condition.item or 'unselected'}"
    if condition.type == "object_enabled":
        return f"When object is enabled: {condition.object_id or 'unselected'}"
    if condition.type == "not":
        return f"Not ({condition_label(condition.condition)})"
    return condition.type


def condition_chip_label(condition: Condition | None) -> str | None:
    if condition is None or condition.type == "always":
        return None
    if condition.type == "has_item":
        return f"Requires: {condition.item or 'item'}"
    if condition.type == "variable":
        return f"Requires: {condition.variable or 'variable'}"
    if condition.type == "object_enabled":
        return f"Requires: {condition.object_id or 'object'}"
    if condition.type == "not":
        nested = condition_chip_label(condition.condition)
        return f"Requires not: {nested.removeprefix('Requires: ') if nested else 'condition'}"
    return f"Requires: {condition.type}"


def effects_label(actions: list[Action]) -> str:
    if not actions:
        return "No effects"
    return ", ".join(action_label(action) for action in actions)


def effect_chip_labels(actions: list[Action]) -> list[str]:
    chips: list[str] = []
    for action in actions:
        if action.type == "give_item":
            chips.append(f"Gives: {action.item or 'item'}")
        elif action.type == "remove_item":
            chips.append(f"Takes: {action.item or 'item'}")
        elif action.type == "set_variable":
            chips.append(f"Sets: {action.variable or 'variable'}")
        elif action.type == "set_object_enabled":
            state = "Enables" if action.enabled else "Disables"
            chips.append(f"{state}: {action.object_id or 'object'}")
        elif action.type == "say":
            chips.append(f"Says: {(action.text or '').strip() or 'line'}")
        else:
            chips.append(action_label(action))
    return chips


def choice_summary(choice: DialogueChoice, npc: NPC, *, simple: bool = True) -> str:
    text = choice.text.strip() or "Empty response"
    target = target_label(npc, choice.target, simple=simple)
    details = []
    if choice.condition is not None:
        details.append(condition_label(choice.condition))
    if choice.actions:
        details.append(effects_label(choice.actions))
    suffix = f" [{' | '.join(details)}]" if details else ""
    return f"{text} -> {target}{suffix}"


def validate_dialogue_graph(npc: NPC) -> list[DialogueValidationIssue]:
    issues: list[DialogueValidationIssue] = []
    node_ids = {node.id for node in npc.dialogue_nodes}
    if not npc.dialogue_nodes:
        return [DialogueValidationIssue("NO_NODES", "This NPC has no conversation cards.")]

    for node in npc.dialogue_nodes:
        if not node.text.strip():
            issues.append(DialogueValidationIssue("EMPTY_NODE_TEXT", "Conversation card text is empty.", node.id))
        for index, choice in enumerate(node.choices):
            if not choice.text.strip():
                issues.append(
                    DialogueValidationIssue("EMPTY_RESPONSE", "Response button text is empty.", node.id, index)
                )
            if choice.target and choice.target not in node_ids:
                issues.append(
                    DialogueValidationIssue(
                        "MISSING_TARGET",
                        f"Response points to missing card: {choice.target}.",
                        node.id,
                        index,
                    )
                )

    reachable = _reachable_node_ids(npc)
    for node in npc.dialogue_nodes:
        if node.id not in reachable:
            issues.append(
                DialogueValidationIssue(
                    "UNREACHABLE_NODE",
                    "Conversation card is not reachable from the first card.",
                    node.id,
                )
            )
    return issues


def format_validation_summary(issues: list[DialogueValidationIssue]) -> str:
    if not issues:
        return "Conversation looks good."
    lines = []
    for issue in issues:
        if issue.code == "EMPTY_NODE_TEXT":
            lines.append("A line is empty.")
        elif issue.code == "EMPTY_RESPONSE":
            lines.append("A reply is empty.")
        elif issue.code == "MISSING_TARGET":
            lines.append("A reply points to a missing line.")
        elif issue.code == "UNREACHABLE_NODE":
            lines.append("A line cannot be reached from the conversation start.")
        elif issue.code == "NO_NODES":
            lines.append("This NPC has no conversation lines yet.")
        else:
            lines.append(issue.message)
    return "\n".join(lines)


def build_dialogue_workspace(dpg, app) -> None:
    with dpg.group(horizontal=True, tag="workspace_panel_dialogue", show=False):
        with dpg.child_window(tag="dialogue_sidebar", width=280, height=-125, border=True):
            dpg.add_text("Dialogue Focus")
            dpg.add_text("Choose an NPC from the current scene to build their conversation.", wrap=240)
            dpg.add_separator()
            dpg.add_text("Current Scene")
            dpg.add_text("", tag="dialogue_scene_name", wrap=240)
            dpg.add_separator()
            dpg.add_text("NPCs In Scene")
            dpg.add_listbox(
                tag="dialogue_npc_list",
                items=[],
                num_items=10,
                width=-1,
                callback=lambda _s, a: app._select_dialogue_npc(dpg, a),
            )
            dpg.add_separator()
            dpg.add_text("", tag="dialogue_npc_summary", wrap=240)

        with dpg.child_window(tag="dialogue_workspace_panel", width=-1, height=-125, border=True):
            dpg.add_text("Dialogue Studio", tag="dialogue_header")
            dpg.add_text(
                "Write a conversation like a screenplay. Expert mode reveals IDs, conditions, and effects when needed.",
                wrap=760,
            )
            with dpg.group(tag="dialogue_composer"):
                with dpg.group(horizontal=True, tag="dialogue_composer_toolbar"):
                    dpg.add_button(
                        label="Add Next Line",
                        tag="dialogue_composer_add_line",
                        callback=lambda: app._composer_add_next_line(dpg),
                    )
                    dpg.add_button(
                        label="Preview Conversation",
                        tag="dialogue_composer_preview",
                        callback=lambda: app._preview_conversation(dpg),
                    )
                dpg.add_text("", tag="dialogue_composer_validation", wrap=760)
                with dpg.child_window(tag="dialogue_composer_panel", height=360, border=True):
                    pass
                dpg.add_text("Branch Overview", tag="dialogue_composer_graph_header")
                with dpg.drawlist(tag="dialogue_graph_overview", width=1, height=220):
                    pass


def refresh_dialogue_workspace(dpg, app, npc: NPC | None) -> None:
    _refresh_dialogue_sidebar(dpg, app, npc)
    dpg.delete_item("dialogue_composer_panel", children_only=True)
    dpg.delete_item("dialogue_graph_overview", children_only=True)
    if npc is None:
        dpg.set_value("dialogue_composer_validation", "Select an NPC to compose a conversation.")
        return
    issues = validate_dialogue_graph(npc)
    dpg.set_value("dialogue_composer_validation", format_validation_summary(issues))
    if not npc.dialogue_nodes:
        dpg.add_text(
            "No conversation lines yet. Add the first line to start the exchange.",
            parent="dialogue_composer_panel",
            wrap=720,
        )
        return
    selected_node_id = app._selected_dialogue_node_id
    if selected_node_id not in {node.id for node in npc.dialogue_nodes}:
        selected_node_id = npc.dialogue_nodes[0].id
        app._selected_dialogue_node_id = selected_node_id
    for card_index, node in enumerate(npc.dialogue_nodes, start=1):
        _build_storyboard_card(dpg, app, npc, node.id, card_index, selected_node_id == node.id)
    _draw_dialogue_graph(dpg, npc)


def _refresh_dialogue_sidebar(dpg, app, npc: NPC | None) -> None:
    scene = app.controller.current_scene
    if dpg.does_item_exist("dialogue_scene_name"):
        dpg.set_value("dialogue_scene_name", "No scene selected." if scene is None else f"{scene.name} ({scene.id})")
    if dpg.does_item_exist("dialogue_npc_list"):
        npc_labels = [] if scene is None else [f"{item.id}: {item.name}" for item in scene.npcs]
        dpg.configure_item("dialogue_npc_list", items=npc_labels)
        if npc_labels:
            selected_id = app.canvas.selected_id if app.canvas.selected_kind == "npc" else scene.npcs[0].id
            selected_label = next((label for label in npc_labels if label.startswith(f"{selected_id}:")), npc_labels[0])
            dpg.set_value("dialogue_npc_list", selected_label)
    if dpg.does_item_exist("dialogue_npc_summary"):
        if npc is None:
            dpg.set_value("dialogue_npc_summary", "No NPC selected.")
        else:
            dpg.set_value(
                "dialogue_npc_summary",
                f"Editing {npc.name} with {len(npc.dialogue_nodes)} line(s).",
            )


def _build_storyboard_card(dpg, app, npc: NPC, node_id: str, card_index: int, selected: bool) -> None:
    node = app._dialogue_node_by_id(node_id)
    if node is None:
        return
    with dpg.child_window(
        parent="dialogue_composer_panel",
        tag=f"studio_card_{node.id}",
        height=290 if app.simple_mode else 420,
        border=True,
    ):
        with dpg.group(horizontal=True):
            title = f"Line {card_index}"
            if selected:
                title = f"{title} (Selected)"
            dpg.add_text(title)
            dpg.add_button(label="Add Next Line", callback=lambda _s=None, _a=None, item=node.id: app._composer_add_next_line(dpg, item))
            dpg.add_button(label="Duplicate Line", callback=lambda _s=None, _a=None, item=node.id: app._studio_duplicate_dialogue_node(dpg, item))
            dpg.add_button(label="Delete Line", callback=lambda _s=None, _a=None, item=node.id: app._studio_delete_dialogue_node(dpg, item))
        if not app.simple_mode:
            dpg.add_input_text(
                tag=f"studio_node_id_{node.id}",
                label="Node ID",
                default_value=node.id,
                width=-1,
                callback=lambda _s=None, _a=None, item=node.id: app._composer_update_dialogue_node(dpg, item),
            )
        dpg.add_input_text(
            tag=f"studio_speaker_{node.id}",
            label="NPC says:",
            default_value=node.speaker,
            width=-1,
            callback=lambda _s=None, _a=None, item=node.id: app._composer_update_dialogue_node(dpg, item),
        )
        dpg.add_input_text(
            tag=f"studio_text_{node.id}",
            label="Line",
            default_value=node.text,
            multiline=True,
            height=74,
            width=-1,
            callback=lambda _s=None, _a=None, item=node.id: app._composer_update_dialogue_node(dpg, item),
        )
        if node.actions and not app.simple_mode:
            dpg.add_text(f"Card effects: {effects_label(node.actions)}", wrap=720)
        dpg.add_text("Replies")
        for choice_index, choice in enumerate(node.choices):
            _build_dialogue_choice_row(dpg, app, npc, node.id, choice_index, choice)
        dpg.add_button(label="Add Reply", callback=lambda _s=None, _a=None, item=node.id: app._studio_add_dialogue_choice(dpg, item))
        if not app.simple_mode:
            _build_advanced_dialogue_tools(dpg, app, npc, node.id)


def _build_dialogue_choice_row(dpg, app, npc: NPC, node_id: str, choice_index: int, choice: DialogueChoice) -> None:
    with dpg.group():
        with dpg.group(horizontal=True):
            dpg.add_spacer(width=20)
            dpg.add_text("Reply:")
            dpg.add_input_text(
                tag=f"studio_choice_text_{node_id}_{choice_index}",
                default_value=choice.text,
                hint="reply text",
                width=240,
                callback=lambda _s=None, _a=None, item=node_id, index=choice_index: app._composer_update_choice_text(dpg, item, index),
            )
            dpg.add_combo(
                tag=f"studio_choice_target_{node_id}_{choice_index}",
                items=DESTINATION_OPTIONS,
                default_value=destination_label(npc, node_id, choice),
                width=150,
                callback=lambda _s=None, _a=None, item=node_id, index=choice_index: app._composer_set_choice_destination(dpg, item, index),
            )
        with dpg.group(horizontal=True):
            dpg.add_spacer(width=20)
            dpg.add_button(label="Up", callback=lambda _s=None, _a=None, item=node_id, index=choice_index: app._composer_move_choice(dpg, item, index, -1))
            dpg.add_button(label="Down", callback=lambda _s=None, _a=None, item=node_id, index=choice_index: app._composer_move_choice(dpg, item, index, 1))
            dpg.add_button(label="Copy", callback=lambda _s=None, _a=None, item=node_id, index=choice_index: app._studio_duplicate_dialogue_choice(dpg, item, index))
            dpg.add_button(label="Delete", callback=lambda _s=None, _a=None, item=node_id, index=choice_index: app._studio_delete_dialogue_choice(dpg, item, index))
        chips = []
        condition_chip = condition_chip_label(choice.condition)
        if condition_chip:
            chips.append(condition_chip)
        chips.extend(effect_chip_labels(choice.actions))
        if chips:
            dpg.add_text("  " + "   ".join(chips), wrap=720)
        if not app.simple_mode:
            dpg.add_text(choice_summary(choice, npc, simple=False), wrap=720)
            _build_choice_advanced_tools(dpg, app, npc, node_id, choice_index, choice)


def _build_advanced_dialogue_tools(dpg, app, npc: NPC, node_id: str) -> None:
    node = app._dialogue_node_by_id(node_id)
    if node is None:
        return
    with dpg.tree_node(label="Advanced line tools", default_open=False):
        dpg.add_text(f"Card ID: {node.id}")
        dpg.add_text("Card actions")
        dpg.add_listbox(
            tag=f"studio_node_action_list_{node.id}",
            items=[f"{index + 1}. {action_label(action)}" for index, action in enumerate(node.actions)],
            num_items=3,
            width=-1,
        )
        with dpg.group(horizontal=True):
            dpg.add_button(label="Add Action", callback=lambda _s=None, _a=None: app._add_dialogue_node_action(dpg))
            dpg.add_button(label="Remove Action", callback=lambda _s=None, _a=None: app._remove_dialogue_node_action(dpg))


def _build_choice_advanced_tools(dpg, app, npc: NPC, node_id: str, choice_index: int, choice: DialogueChoice) -> None:
    prefix = f"studio_choice_condition_{node_id}_{choice_index}"
    scene = app.controller.current_scene
    project = app.controller.project
    item_ids = [item.id for item in project.items] if project is not None else []
    object_ids = []
    if scene is not None:
        object_ids = [
            *(item.id for item in scene.hotspots),
            *(item.id for item in scene.exits),
            *(item.id for item in scene.npcs),
            *(item.id for item in scene.items),
            *(item.id for item in scene.spawns),
        ]
    with dpg.tree_node(label="Advanced reply tools", default_open=False):
        dpg.add_text(f"Actual target: {choice.target or 'End conversation'}", wrap=720)
        dpg.add_combo(
            tag=f"studio_choice_target_raw_{node_id}_{choice_index}",
            label="Target Card",
            items=["", *(node.id for node in npc.dialogue_nodes)],
            default_value=choice.target or "",
            width=-1,
            callback=lambda _s=None, _a=None, item=node_id, index=choice_index: app._studio_apply_dialogue_choice(dpg, item, index),
        )
        dpg.add_text(f"Condition: {condition_label(choice.condition)}", wrap=720)
        dpg.add_combo(
            tag=f"{prefix}_type",
            label="Condition",
            items=CONDITION_TYPES,
            default_value=choice.condition.type if choice.condition is not None else "always",
            width=-1,
        )
        dpg.add_input_text(
            tag=f"{prefix}_variable",
            label="Variable",
            default_value="" if choice.condition is None else choice.condition.variable or "",
            width=-1,
        )
        dpg.add_combo(
            tag=f"{prefix}_operator",
            label="Operator",
            items=CONDITION_OPERATORS,
            default_value="==" if choice.condition is None else choice.condition.operator,
            width=-1,
        )
        dpg.add_input_text(
            tag=f"{prefix}_value",
            label="Value",
            default_value="true" if choice.condition is None else str(choice.condition.value),
            width=-1,
        )
        dpg.add_combo(tag=f"{prefix}_item", label="Item", items=item_ids, width=-1)
        dpg.add_combo(tag=f"{prefix}_object", label="Object", items=object_ids, width=-1)
        dpg.add_combo(
            tag=f"{prefix}_not_type",
            label="Not Condition",
            items=CONDITION_TYPES[:-1],
            default_value="always",
            width=-1,
        )
        app._set_condition_fields(dpg, prefix, choice.condition)
        dpg.add_button(
            label="Apply Condition",
            callback=lambda _s=None, _a=None, item=node_id, index=choice_index: app._studio_apply_choice_condition(dpg, item, index),
        )
        dpg.add_separator()
        dpg.add_text(f"Effects: {effects_label(choice.actions)}", wrap=720)
        for effect_index, action in enumerate(choice.actions):
            _build_dialogue_choice_effect_editor(dpg, app, npc, node_id, choice_index, effect_index, action, item_ids, object_ids)
        with dpg.group(horizontal=True):
            dpg.add_button(
                label="Add Effect",
                callback=lambda _s=None, _a=None, item=node_id, index=choice_index: app._studio_add_choice_effect(dpg, item, index),
            )
            dpg.add_button(
                label="Remove Last Effect",
                callback=lambda _s=None, _a=None, item=node_id, index=choice_index: app._studio_remove_choice_effect(dpg, item, index),
            )


def _build_dialogue_choice_effect_editor(
    dpg,
    app,
    npc: NPC,
    node_id: str,
    choice_index: int,
    effect_index: int,
    action: Action,
    item_ids: list[str],
    object_ids: list[str],
) -> None:
    scene_ids = list(app.controller.scenes.keys())
    node_ids = [node.id for node in npc.dialogue_nodes]
    prefix = f"studio_choice_effect_{node_id}_{choice_index}_{effect_index}"
    with dpg.tree_node(label=f"Effect {effect_index + 1}: {action_label(action)}", default_open=False):
        dpg.add_combo(tag=f"{prefix}_type", label="Effect Type", items=ACTION_TYPES, default_value=action.type, width=-1)
        dpg.add_input_text(tag=f"{prefix}_speaker", label="Speaker", default_value=action.speaker or "", width=-1)
        dpg.add_input_text(tag=f"{prefix}_text", label="Text", default_value=action.text or "", width=-1)
        dpg.add_combo(tag=f"{prefix}_npc", label="NPC", items=[app.canvas.selected_id or ""], default_value=action.npc or "", width=-1)
        dpg.add_combo(tag=f"{prefix}_node", label="Dialogue Card", items=node_ids, default_value=action.node or "", width=-1)
        dpg.add_combo(tag=f"{prefix}_scene", label="Scene", items=scene_ids, default_value=action.scene or "", width=-1)
        dpg.add_combo(tag=f"{prefix}_spawn", label="Spawn", items=[], default_value=action.spawn or "", width=-1)
        dpg.add_combo(tag=f"{prefix}_item", label="Item", items=item_ids, default_value=action.item or "", width=-1)
        dpg.add_combo(tag=f"{prefix}_object", label="Object", items=object_ids, default_value=action.object_id or "", width=-1)
        dpg.add_input_text(tag=f"{prefix}_variable", label="Variable", default_value=action.variable or "", width=-1)
        dpg.add_input_text(tag=f"{prefix}_value", label="Value", default_value="" if action.value is None else str(action.value), width=-1)
        dpg.add_checkbox(tag=f"{prefix}_enabled", label="Enabled", default_value=bool(action.enabled))
        with dpg.group(horizontal=True):
            dpg.add_button(
                label="Apply Effect",
                callback=lambda _s=None, _a=None, item=node_id, index=choice_index, effect=effect_index: app._studio_apply_choice_effect(dpg, item, index, effect),
            )
            dpg.add_button(
                label="Remove Effect",
                callback=lambda _s=None, _a=None, item=node_id, index=choice_index, effect=effect_index: app._studio_remove_choice_effect_at(dpg, item, index, effect),
            )


def _draw_dialogue_graph(dpg, npc: NPC) -> None:
    node_width = 150
    positions = {}
    for index, node in enumerate(npc.dialogue_nodes):
        x = 20 + (index % 4) * 185
        y = 30 + (index // 4) * 70
        positions[node.id] = (x, y)
        dpg.draw_rectangle((x, y), (x + node_width, y + 42), color=(110, 140, 170), parent="dialogue_graph_overview")
        dpg.draw_text((x + 8, y + 12), f"{index + 1}. {node.speaker}", size=14, parent="dialogue_graph_overview")
    for node in npc.dialogue_nodes:
        start = positions.get(node.id)
        if start is None:
            continue
        for choice in node.choices:
            if choice.target not in positions:
                continue
            end = positions[choice.target]
            dpg.draw_line((start[0] + node_width, start[1] + 21), (end[0], end[1] + 21), color=(220, 180, 90), parent="dialogue_graph_overview")
    dpg.configure_item("dialogue_graph_overview", width=760, height=max(220, 70 + ((len(npc.dialogue_nodes) + 3) // 4) * 70))


def _reachable_node_ids(npc: NPC) -> set[str]:
    if not npc.dialogue_nodes:
        return set()
    node_by_id = {node.id: node for node in npc.dialogue_nodes}
    reachable = {npc.dialogue_nodes[0].id}
    pending = [npc.dialogue_nodes[0].id]
    while pending:
        node_id = pending.pop()
        node = node_by_id.get(node_id)
        if node is None:
            continue
        for choice in node.choices:
            if choice.target and choice.target in node_by_id and choice.target not in reachable:
                reachable.add(choice.target)
                pending.append(choice.target)
    return reachable
