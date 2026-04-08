from __future__ import annotations

import json

from aqt import gui_hooks, mw

from .runtime import (
    addon_web_base_url,
    read_window_layout,
    register_web_exports,
    write_window_layout,
)
from .service import get_service

COMMAND_PREFIX = "anki-slot-machine"
_registered = False


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
    if not message.startswith(f"{COMMAND_PREFIX}:"):
        return handled_result

    payload = message[len(f"{COMMAND_PREFIX}:") :]
    action, value = payload.split(":", 1) if ":" in payload else (payload, None)

    if action == "refresh":
        snapshot = get_service().snapshot(
            card_id=_current_card_id(context),
            answer_button_count=_answer_button_count(context),
        )
    elif action == "saveLayout" and value is not None:
        try:
            decoded = json.loads(value)
        except ValueError:
            return handled_result
        if isinstance(decoded, dict):
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
        refresh_active_reviewer()


def refresh_active_reviewer() -> None:
    reviewer = getattr(mw, "reviewer", None)
    if not reviewer or getattr(reviewer, "card", None) is None:
        return
    _push_snapshot(
        reviewer,
        get_service().snapshot(
            card_id=_current_card_id(reviewer),
            answer_button_count=_answer_button_count(reviewer),
        ),
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


def _push_snapshot(reviewer, snapshot: dict) -> None:
    web = getattr(reviewer, "web", None)
    if not web:
        return
    enriched_snapshot = dict(snapshot)
    layout = read_window_layout()
    if layout is not None:
        enriched_snapshot["window_layout"] = layout
    payload = json.dumps(enriched_snapshot, ensure_ascii=False)
    web.eval(
        "window.AnkiSlotMachine && " f"window.AnkiSlotMachine.syncState({payload});"
    )


def _is_review_undo(changes) -> bool:
    nested_changes = getattr(changes, "changes", changes)
    return bool(getattr(nested_changes, "study_queues", False))
