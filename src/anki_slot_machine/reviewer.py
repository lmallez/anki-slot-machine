from __future__ import annotations

import json

from aqt import gui_hooks, mw

from .config import (
    add_machine_to_config,
    close_all_machines_in_config,
    remove_machine_from_config,
)
from .runtime import (
    addon_config,
    addon_instance_key,
    addon_web_base_url,
    delete_window_layout,
    read_window_layout,
    read_window_layouts,
    register_web_exports,
    write_addon_config,
    write_window_layout,
)
from .service import get_service
from .ui.stats_dialog import show_stats_dialog

_registered = False


def _command_prefix() -> str:
    return f"anki-slot-machine:{addon_instance_key()}"


def register() -> None:
    global _registered

    if _registered:
        return

    register_web_exports()
    gui_hooks.webview_will_set_content.append(on_webview_will_set_content)
    gui_hooks.webview_did_receive_js_message.append(on_webview_did_receive_js_message)
    gui_hooks.reviewer_did_show_question.append(on_reviewer_did_show_question)
    gui_hooks.reviewer_did_answer_card.append(on_reviewer_did_answer_card)
    if hasattr(gui_hooks, "state_did_undo"):
        gui_hooks.state_did_undo.append(on_state_did_undo)
    _registered = True


def on_webview_will_set_content(web_content, context) -> None:
    if not _is_reviewer_context(context):
        return

    base_url = addon_web_base_url()
    css_path = f"{base_url}/slot_machine.css"
    js_path = f"{base_url}/slot_machine.js"
    if css_path not in web_content.css:
        web_content.css.append(css_path)
    if js_path not in web_content.js:
        web_content.js.append(js_path)


def on_webview_did_receive_js_message(handled_result, message: str, context):
    handled, result = handled_result
    if handled or not _is_reviewer_context(context):
        return handled_result
    command_prefix = _command_prefix()
    if not message.startswith(f"{command_prefix}:"):
        return handled_result

    payload = message[len(f"{command_prefix}:") :]
    action, value = payload.split(":", 1) if ":" in payload else (payload, None)

    if action == "refresh":
        snapshot = get_service().snapshot(
            card_id=_current_card_id(context),
            answer_button_count=_answer_button_count(context),
        )
    elif action == "addSlot":
        write_addon_config(add_machine_to_config(addon_config()))
        snapshot = get_service().snapshot(
            card_id=_current_card_id(context),
            answer_button_count=_answer_button_count(context),
        )
    elif action == "closeAllSlots":
        current_config = addon_config()
        updated_config = close_all_machines_in_config(current_config)
        if updated_config != current_config:
            removed_machine_keys = {
                machine.get("key")
                for machine in current_config.get("machines", [])
                if isinstance(machine, dict) and isinstance(machine.get("key"), str)
            } - {
                machine.get("key")
                for machine in updated_config.get("machines", [])
                if isinstance(machine, dict) and isinstance(machine.get("key"), str)
            }
            write_addon_config(updated_config)
            for machine_key in removed_machine_keys:
                delete_window_layout(machine_key)
        snapshot = get_service().snapshot(
            card_id=_current_card_id(context),
            answer_button_count=_answer_button_count(context),
        )
    elif action == "removeSlot" and value is not None:
        current_config = addon_config()
        updated_config = remove_machine_from_config(current_config, value)
        if updated_config != current_config:
            write_addon_config(updated_config)
            delete_window_layout(value)
        snapshot = get_service().snapshot(
            card_id=_current_card_id(context),
            answer_button_count=_answer_button_count(context),
        )
    elif action == "showStats":
        show_stats_dialog()
        return True, None
    elif action == "saveLayout" and value is not None:
        try:
            decoded = json.loads(value)
        except ValueError:
            return handled_result
        if isinstance(decoded, dict):
            machine_key = decoded.get("machine_key")
            layout = decoded.get("layout")
            if isinstance(machine_key, str) and isinstance(layout, dict):
                write_window_layout(layout, machine_key)
                return True, None
            write_window_layout(decoded)
            return True, None
        return handled_result
    else:
        return handled_result

    _push_snapshot(context, snapshot)
    return True, None


def on_reviewer_did_show_question(card) -> None:
    reviewer = getattr(mw, "reviewer", None)
    if not reviewer or getattr(reviewer, "card", None) is None:
        return
    _push_snapshot(
        reviewer,
        get_service().snapshot(
            card_id=getattr(card, "id", None),
            answer_button_count=_answer_button_count(reviewer),
        ),
    )


def on_reviewer_did_answer_card(reviewer, card, ease: int) -> None:
    button_count = _answer_button_count(reviewer, card)
    get_service().apply_review(card_id=card.id, ease=ease, button_count=button_count)


def on_state_did_undo(changes) -> None:
    if not _is_review_undo(changes):
        return
    if get_service().undo_last_review():
        refresh_active_reviewer(suppress_animation=True)


def refresh_active_reviewer(*, suppress_animation: bool = False) -> None:
    reviewer = getattr(mw, "reviewer", None)
    if not reviewer or getattr(reviewer, "card", None) is None:
        return
    _push_snapshot(
        reviewer,
        get_service().snapshot(
            card_id=_current_card_id(reviewer),
            answer_button_count=_answer_button_count(reviewer),
        ),
        suppress_animation=suppress_animation,
    )


def _is_reviewer_context(context) -> bool:
    return bool(
        context
        and hasattr(context, "web")
        and (hasattr(context, "card") or hasattr(context, "mw"))
    )


def _current_card_id(reviewer) -> int | None:
    card = getattr(reviewer, "card", None)
    return getattr(card, "id", None)


def _answer_button_count(reviewer, card=None) -> int:
    active_card = card or getattr(reviewer, "card", None)
    if not active_card:
        return 4
    try:
        return reviewer.mw.col.sched.answerButtons(active_card)
    except Exception:
        return 4


def _push_snapshot(
    reviewer, snapshot: dict, *, suppress_animation: bool = False
) -> None:
    web = getattr(reviewer, "web", None)
    if not web:
        return
    enriched_snapshot = dict(snapshot)
    if suppress_animation:
        enriched_snapshot["suppress_animation"] = True
    layouts = read_window_layouts()
    if layouts:
        enriched_snapshot["window_layouts"] = layouts
        if "main" in layouts:
            enriched_snapshot["window_layout"] = layouts["main"]
    else:
        layout = read_window_layout()
        if layout is not None:
            enriched_snapshot["window_layout"] = layout
    payload = json.dumps(enriched_snapshot, ensure_ascii=False)
    instance_key = json.dumps(addon_instance_key(), ensure_ascii=False)
    web.eval(
        "window.AnkiSlotMachineInstances && "
        f"window.AnkiSlotMachineInstances[{instance_key}] && "
        f"window.AnkiSlotMachineInstances[{instance_key}].syncState({payload});"
    )


def _is_review_undo(changes) -> bool:
    nested_changes = getattr(changes, "changes", changes)
    return bool(getattr(nested_changes, "study_queues", False))
