from __future__ import annotations

from aqt import gui_hooks

from .menu import register as register_menu
from .reviewer import register as register_reviewer

_registered = False
_menu_hook_registered = False


def register() -> None:
    global _registered, _menu_hook_registered

    if _registered:
        return

    register_reviewer()
    if hasattr(gui_hooks, "main_window_did_init"):
        if not _menu_hook_registered:
            gui_hooks.main_window_did_init.append(register_menu)
            _menu_hook_registered = True
    else:
        register_menu()
    _registered = True
