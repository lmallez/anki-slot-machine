from __future__ import annotations

from aqt import mw
from aqt.qt import QAction, QMenu
from aqt.utils import askUser, showText

from .reviewer import refresh_active_reviewer
from .service import get_service
from .ui.odds_dialog import show_odds_dialog
from .ui.settings_dialog import show_settings_dialog
from .ui.stats_dialog import show_stats_dialog

_registered = False


def register() -> None:
    global _registered

    if _registered:
        return

    menu = QMenu("Slot Machine", mw)

    stats_action = QAction("Show Stats", mw)
    stats_action.triggered.connect(show_stats_dialog)
    menu.addAction(stats_action)

    odds_action = QAction("Show Odds and Rewards", mw)
    odds_action.triggered.connect(show_odds_dialog)
    menu.addAction(odds_action)

    reset_action = QAction("Reset Balance and Stats", mw)
    reset_action.triggered.connect(_reset_progress)
    menu.addAction(reset_action)

    quick_settings_action = QAction("Quick Settings", mw)
    quick_settings_action.triggered.connect(show_settings_dialog)
    menu.addAction(quick_settings_action)

    settings_action = QAction("Settings Help", mw)
    settings_action.triggered.connect(_show_settings_help)
    menu.addAction(settings_action)

    mw.form.menuTools.addMenu(menu)
    _registered = True


def _reset_progress() -> None:
    if not askUser("Reset the fake balance, streak, and slot-machine history?"):
        return

    get_service().reset_progress()
    refresh_active_reviewer()


def _show_settings_help() -> None:
    showText(
        "Edit this add-on's configuration in Tools -> Add-ons -> Anki Slot Machine "
        "-> Config.\n\n"
        "The config editor controls the starting balance, decimal precision, "
        "signed answer base values, the shared slot profile, and the list of "
        "slot-machine windows shown in the reviewer.\n\n"
        "All answer buttons use the same shared-stack behavior. Each review adds "
        "its configured value into the current stack, and the Nth review settles "
        "that full stack. If the spin-chance check passes, the machine rolls on "
        "the full stacked value. If it fails, the stacked value is paid out "
        "directly instead. Any answer with a configured value of 0 adds nothing "
        "to the stack."
    )
