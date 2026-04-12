from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
_ADDON_MODULES_RESET = False


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
        self._plain_text_updates = 0
        self._minimum_height = None
        self._minimum_width = None
        self._mouse_tracking = False
        self._stylesheet = ""
        self._visible = True

    def setWordWrap(self, *_args, **_kwargs) -> None:
        return None

    def setReadOnly(self, *_args, **_kwargs) -> None:
        return None

    def setMinimumHeight(self, value: int) -> None:
        self._minimum_height = value

    def setMinimumWidth(self, value: int) -> None:
        self._minimum_width = value

    def setStyleSheet(self, stylesheet: str) -> None:
        self._stylesheet = stylesheet

    def update(self) -> None:
        return None

    def setMouseTracking(self, value: bool) -> None:
        self._mouse_tracking = value

    def width(self) -> int:
        return 320

    def height(self) -> int:
        return 220

    def setText(self, text: str) -> None:
        self._text = text

    def setPlainText(self, text: str) -> None:
        self._text = text
        self._plain_text_updates += 1

    def setVisible(self, value: bool) -> None:
        self._visible = value

    def setContentsMargins(self, *_args, **_kwargs) -> None:
        return None


class _QLabel(_BaseWidget):
    pass


class _QPlainTextEdit(_BaseWidget):
    pass


class _QWidget(_BaseWidget):
    pass


class _QFrame(_BaseWidget):
    pass


class _QColor:
    def __init__(self, *_args, **_kwargs) -> None:
        pass


class _QPen:
    def __init__(self, *_args, **_kwargs) -> None:
        pass


class _QPainter:
    class RenderHint:
        Antialiasing = 1

    def __init__(self, *_args, **_kwargs) -> None:
        pass

    def setRenderHint(self, *_args, **_kwargs) -> None:
        return None

    def fillRect(self, *_args, **_kwargs) -> None:
        return None

    def setPen(self, *_args, **_kwargs) -> None:
        return None

    def drawRect(self, *_args, **_kwargs) -> None:
        return None

    def drawText(self, *_args, **_kwargs) -> None:
        return None

    def drawLine(self, *_args, **_kwargs) -> None:
        return None


class _QToolTip:
    @staticmethod
    def showText(*_args, **_kwargs) -> None:
        return None


class _QPushButton(_BaseWidget):
    def __init__(self, *_args, **_kwargs) -> None:
        super().__init__()
        self.clicked = _Signal()


class _SpinBox(_BaseWidget):
    def __init__(self, *_args, **_kwargs) -> None:
        super().__init__()
        self._minimum = 0
        self._maximum = 99
        self._value = 0
        self._single_step = 1

    def setRange(self, minimum: int, maximum: int) -> None:
        self._minimum = minimum
        self._maximum = maximum

    def setMinimum(self, minimum: int) -> None:
        self._minimum = minimum

    def setMaximum(self, maximum: int) -> None:
        self._maximum = maximum

    def setSingleStep(self, value: int) -> None:
        self._single_step = value

    def setValue(self, value: int) -> None:
        self._value = max(self._minimum, min(self._maximum, int(value)))

    def value(self) -> int:
        return self._value


class _DoubleSpinBox(_SpinBox):
    def __init__(self, *_args, **_kwargs) -> None:
        super().__init__()
        self._decimals = 2
        self._minimum = 0.0
        self._maximum = 99.0
        self._value = 0.0
        self._single_step = 1.0

    def setDecimals(self, value: int) -> None:
        self._decimals = value

    def setRange(self, minimum: float, maximum: float) -> None:
        self._minimum = minimum
        self._maximum = maximum

    def setMinimum(self, minimum: float) -> None:
        self._minimum = minimum

    def setMaximum(self, maximum: float) -> None:
        self._maximum = maximum

    def setSingleStep(self, value: float) -> None:
        self._single_step = value

    def setValue(self, value: float) -> None:
        self._value = max(self._minimum, min(self._maximum, float(value)))

    def value(self) -> float:
        return self._value


class _Layout:
    def __init__(self, *_args, **_kwargs) -> None:
        self.children = []
        self.spacing = None

    def addWidget(self, widget, *_args) -> None:
        self.children.append(widget)

    def addLayout(self, layout, *_args) -> None:
        self.children.append(layout)

    def addRow(self, *items) -> None:
        self.children.append(items)

    def addStretch(self, stretch) -> None:
        self.children.append(stretch)

    def setSpacing(self, value: int) -> None:
        self.spacing = value

    def setContentsMargins(self, *_args, **_kwargs) -> None:
        return None


class _QTimer:
    def __init__(self, *_args, **_kwargs) -> None:
        self.timeout = _Signal()
        self.interval = None
        self.running = False

    def setInterval(self, value: int) -> None:
        self.interval = value

    def start(self) -> None:
        self.running = True

    @staticmethod
    def singleShot(_ms, callback) -> None:
        if callable(callback):
            callback()


class _QDialog:
    def __init__(self, *_args, **_kwargs) -> None:
        self.window_title = ""
        self.size = None
        self.stylesheet = ""
        self.visible = False

    def setWindowTitle(self, title: str) -> None:
        self.window_title = title

    def resize(self, width: int, height: int) -> None:
        self.size = (width, height)

    def setStyleSheet(self, stylesheet: str) -> None:
        self.stylesheet = stylesheet

    def exec(self) -> int:
        return 0

    def accept(self) -> None:
        return None

    def close(self) -> None:
        self.visible = False

    def show(self) -> None:
        self.visible = True

    def showNormal(self) -> None:
        self.visible = True

    def raise_(self) -> None:
        return None

    def activateWindow(self) -> None:
        return None


class _Reviewer:
    pass


def install_stubs() -> SimpleNamespace:
    global _ADDON_MODULES_RESET

    if str(SRC) not in sys.path:
        sys.path.insert(0, str(SRC))

    if not _ADDON_MODULES_RESET:
        for name in list(sys.modules):
            if name == "anki_slot_machine" or name.startswith("anki_slot_machine."):
                del sys.modules[name]
        _ADDON_MODULES_RESET = True

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
        state_did_undo=[],
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
    qt_module.QDoubleSpinBox = _DoubleSpinBox
    qt_module.QFrame = _QFrame
    qt_module.QFormLayout = _Layout
    qt_module.QGridLayout = _Layout
    qt_module.QHBoxLayout = _Layout
    qt_module.QLabel = _QLabel
    qt_module.QPlainTextEdit = _QPlainTextEdit
    qt_module.QPushButton = _QPushButton
    qt_module.QSpinBox = _SpinBox
    qt_module.QTimer = _QTimer
    qt_module.QVBoxLayout = _Layout
    qt_module.QWidget = _QWidget
    qt_module.QColor = _QColor
    qt_module.QPen = _QPen
    qt_module.QPainter = _QPainter
    qt_module.QToolTip = _QToolTip

    utils_module = ModuleType("aqt.utils")
    utils_module.askUser = lambda *_args, **_kwargs: True
    utils_module.showText = lambda *_args, **_kwargs: None

    sys.modules["aqt"] = aqt
    sys.modules["aqt.reviewer"] = reviewer_module
    sys.modules["aqt.qt"] = qt_module
    sys.modules["aqt.utils"] = utils_module

    return SimpleNamespace(mw=mw, gui_hooks=gui_hooks, reviewer_class=_Reviewer)
