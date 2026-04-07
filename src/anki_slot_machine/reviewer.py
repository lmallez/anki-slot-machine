from __future__ import annotations

import json

from aqt import gui_hooks, mw

from .runtime import addon_web_base_url, register_web_exports
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

    _, action, *rest = message.split(":")
    payload = rest[0] if rest else None
    service = get_service()

    if action == "refresh":
        snapshot = service.snapshot(
            card_id=_current_card_id(context),
            answer_button_count=_answer_button_count(context),
        )
    elif action == "set-bet":
        snapshot = service.set_bet(payload)
    elif action == "change-bet":
        snapshot = service.change_bet(payload)
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
    payload = json.dumps(snapshot, ensure_ascii=False)
    web.eval(
        "window.AnkiSlotMachine && " f"window.AnkiSlotMachine.syncState({payload});"
    )
