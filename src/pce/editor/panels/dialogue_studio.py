from __future__ import annotations

from dataclasses import dataclass

from pce.editor.panels.visual_editors import action_label
from pce.shared.models import Action, Condition, DialogueChoice, NPC


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


def effects_label(actions: list[Action]) -> str:
    if not actions:
        return "No effects"
    return ", ".join(action_label(action) for action in actions)


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
            issues.append(
                DialogueValidationIssue("EMPTY_NODE_TEXT", "Conversation card text is empty.", node.id)
            )
        for index, choice in enumerate(node.choices):
            if not choice.text.strip():
                issues.append(
                    DialogueValidationIssue(
                        "EMPTY_RESPONSE",
                        "Response button text is empty.",
                        node.id,
                        index,
                    )
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


def build_dialogue_studio(dpg, app) -> None:
    with dpg.child_window(tag="dialogue_studio_panel", width=-390, height=-125, border=True):
        with dpg.group(horizontal=True):
            dpg.add_text("Dialogue Studio", tag="dialogue_studio_title")
            dpg.add_button(label="Add Card", callback=lambda: app._studio_add_dialogue_node(dpg))
            dpg.add_button(label="Preview Conversation", callback=lambda: app._preview_conversation(dpg))
        dpg.add_text("", tag="dialogue_studio_validation", wrap=760)
        dpg.add_separator()
        with dpg.group(tag="dialogue_storyboard"):
            pass
        dpg.add_separator()
        dpg.add_text("Branch Overview")
        with dpg.drawlist(tag="dialogue_graph_overview", width=1, height=180):
            pass
