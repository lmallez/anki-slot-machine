from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


class _Signal:
    def __init__(self) -> None:
        self._callbacks = []

    def connect(self, callback) -> None:
        self._callbacks.append(callback)


class _QAction:
    def __init__(self, *_args, **_kwargs) -> None:
        self.triggered = _Signal()


class _QMenu:
    def __init__(self, *_args, **_kwargs) -> None:
        self.actions = []

    def addAction(self, action) -> None:
        self.actions.append(action)


class _BaseWidget:
    def __init__(self, *_args, **_kwargs) -> None:
        self._text = ""

    def setWordWrap(self, *_args, **_kwargs) -> None:
        return None

    def setReadOnly(self, *_args, **_kwargs) -> None:
        return None

    def setText(self, text: str) -> None:
        self._text = text

    def setPlainText(self, text: str) -> None:
        self._text = text


class _QLabel(_BaseWidget):
    pass


class _QPlainTextEdit(_BaseWidget):
    pass


class _QPushButton(_BaseWidget):
    def __init__(self, *_args, **_kwargs) -> None:
        super().__init__()
        self.clicked = _Signal()


class _Layout:
    def __init__(self, *_args, **_kwargs) -> None:
        self.children = []

    def addWidget(self, widget) -> None:
        self.children.append(widget)

    def addLayout(self, layout) -> None:
        self.children.append(layout)

    def addStretch(self, stretch) -> None:
        self.children.append(stretch)


class _QDialog:
    def __init__(self, *_args, **_kwargs) -> None:
        self.window_title = ""
        self.size = None

    def setWindowTitle(self, title: str) -> None:
        self.window_title = title

    def resize(self, width: int, height: int) -> None:
        self.size = (width, height)

    def exec(self) -> int:
        return 0

    def accept(self) -> None:
        return None


class _Reviewer:
    pass


def install_stubs() -> SimpleNamespace:
    if str(SRC) not in sys.path:
        sys.path.insert(0, str(SRC))

    for name in list(sys.modules):
        if name == "anki_slot_machine" or name.startswith("anki_slot_machine."):
            del sys.modules[name]

    for name in ("aqt", "aqt.reviewer", "aqt.qt", "aqt.utils"):
        sys.modules.pop(name, None)

    addon_manager = SimpleNamespace(
        getConfig=lambda _module: {},
        writeConfig=lambda _module, _config: None,
        setWebExports=lambda _module, _pattern: None,
        addonFromModule=lambda _module: "anki_slot_machine",
        addonsFolder=lambda: str(ROOT / ".test_addons"),
    )
    menu_tools = SimpleNamespace(menus=[], addMenu=lambda menu: menu_tools.menus.append(menu))
    col = SimpleNamespace(sched=SimpleNamespace(answerButtons=lambda _card: 4))
    mw = SimpleNamespace(
        addonManager=addon_manager,
        form=SimpleNamespace(menuTools=menu_tools),
        col=col,
        reviewer=None,
    )

    gui_hooks = SimpleNamespace(
        webview_will_set_content=[],
        webview_did_receive_js_message=[],
        reviewer_did_show_question=[],
        reviewer_did_answer_card=[],
        main_window_did_init=[],
    )

    aqt = ModuleType("aqt")
    aqt.mw = mw
    aqt.gui_hooks = gui_hooks

    reviewer_module = ModuleType("aqt.reviewer")
    reviewer_module.Reviewer = _Reviewer

    qt_module = ModuleType("aqt.qt")
    qt_module.QAction = _QAction
    qt_module.QMenu = _QMenu
    qt_module.QDialog = _QDialog
    qt_module.QHBoxLayout = _Layout
    qt_module.QLabel = _QLabel
    qt_module.QPlainTextEdit = _QPlainTextEdit
    qt_module.QPushButton = _QPushButton
    qt_module.QVBoxLayout = _Layout

    utils_module = ModuleType("aqt.utils")
    utils_module.askUser = lambda *_args, **_kwargs: True
    utils_module.showText = lambda *_args, **_kwargs: None

    sys.modules["aqt"] = aqt
    sys.modules["aqt.reviewer"] = reviewer_module
    sys.modules["aqt.qt"] = qt_module
    sys.modules["aqt.utils"] = utils_module

    return SimpleNamespace(mw=mw, gui_hooks=gui_hooks, reviewer_class=_Reviewer)
