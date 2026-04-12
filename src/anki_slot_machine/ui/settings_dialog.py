from __future__ import annotations

from aqt import mw
from aqt.qt import (
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..config import config_from_raw
from ..runtime import addon_config, write_addon_config


ANSWER_KEYS = ("again", "hard", "good", "easy")


def build_settings_config(
    raw_config: dict | None,
    *,
    answer_base_values: dict[str, float],
    spin_trigger_chance: float,
    spin_trigger_every_n: int,
) -> dict:
    source = dict(raw_config or {})
    existing_answer_values = source.get("answer_base_values")

    merged = (
        dict(existing_answer_values) if isinstance(existing_answer_values, dict) else {}
    )
    for key in ANSWER_KEYS:
        if key in answer_base_values:
            merged[key] = float(answer_base_values[key])

    source["answer_base_values"] = merged
    source["spin_trigger_chance"] = float(spin_trigger_chance)
    source["spin_trigger_every_n"] = int(spin_trigger_every_n)
    return source


class SlotMachineSettingsDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent or mw)

        self.setWindowTitle("Slot Machine Settings")
        self.resize(480, 460)

        self.setStyleSheet(
            """
            QDialog {
                background: #151617;
                color: #f2f2ed;
            }
            QLabel {
                color: #f2f2ed;
            }
            QPushButton {
                min-width: 88px;
                padding: 6px 12px;
            }
            QSpinBox, QDoubleSpinBox {
                min-width: 180px;
                min-height: 24px;
                padding: 2px 8px;
                background: #232527;
                color: #f2f2ed;
                border: 1px solid #4b4031;
                border-radius: 6px;
            }
            """
        )

        self._raw_config = addon_config()
        self._config = config_from_raw(self._raw_config)

        answer_decimals = max(2, self._config.decimal_places)

        root = QVBoxLayout(self)
        root.setSpacing(14)

        root.addWidget(QLabel("<b>Quick Slot Settings</b>"))
        intro = QLabel("Change rewards and spin frequency here.")
        intro.setWordWrap(True)
        root.addWidget(intro)

        root.addWidget(QLabel("<b>Answer Rewards</b>"))

        help_rewards = QLabel(
            "Positive values give money when you answer.\n"
            "Negative values subtract money as a penalty.\n"
            "0 disables any reward or penalty for that answer."
        )
        help_rewards.setWordWrap(True)
        root.addWidget(help_rewards)

        form = QFormLayout()
        form.setSpacing(12)

        self.again_input = self._build_answer_input(
            self._config.answer_base_values["again"], answer_decimals
        )
        form.addRow("Again", self.again_input)

        self.hard_input = self._build_answer_input(
            self._config.answer_base_values["hard"], answer_decimals
        )
        form.addRow("Hard", self.hard_input)

        self.good_input = self._build_answer_input(
            self._config.answer_base_values["good"], answer_decimals
        )
        form.addRow("Good", self.good_input)

        self.easy_input = self._build_answer_input(
            self._config.answer_base_values["easy"], answer_decimals
        )
        form.addRow("Easy", self.easy_input)

        root.addLayout(form)

        root.addWidget(QLabel("<b>Spin Trigger</b>"))

        trigger_help = QLabel("Controls how often Good/Easy answers trigger a spin.")
        trigger_help.setWordWrap(True)
        root.addWidget(trigger_help)

        trigger_form = QFormLayout()
        trigger_form.setSpacing(12)

        self.spin_trigger_chance_input = QDoubleSpinBox(self)
        self.spin_trigger_chance_input.setDecimals(3)
        self.spin_trigger_chance_input.setRange(0.0, 1.0)
        self.spin_trigger_chance_input.setSingleStep(0.05)
        self.spin_trigger_chance_input.setValue(self._config.spin_trigger_chance)

        trigger_form.addRow(
            "Chance",
            self._field(
                self.spin_trigger_chance_input,
                "Probability (0.0–1.0) that a spin happens.",
            ),
        )

        self.spin_trigger_every_n_input = QSpinBox(self)
        self.spin_trigger_every_n_input.setRange(1, 999)
        self.spin_trigger_every_n_input.setValue(self._config.spin_trigger_every_n)

        trigger_form.addRow(
            "Every N",
            self._field(
                self.spin_trigger_every_n_input,
                "Number of reviews before checking spin chance.",
            ),
        )

        root.addLayout(trigger_form)

        footer = QLabel("Tip: chance=1.0 and every N=1 → always spins.")
        footer.setWordWrap(True)
        root.addWidget(footer)

        buttons = QHBoxLayout()
        buttons.addStretch(1)

        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.close)

        save = QPushButton("Save")
        save.clicked.connect(self.save)

        buttons.addWidget(cancel)
        buttons.addWidget(save)

        root.addLayout(buttons)

    def _build_answer_input(self, value: float, decimals: int) -> QDoubleSpinBox:
        w = QDoubleSpinBox(self)
        w.setDecimals(decimals)
        w.setRange(-9999.0, 9999.0)
        w.setSingleStep(0.25)
        w.setValue(float(value))
        return w

    def _field(self, input_widget, help_text: str) -> QWidget:
        container = QWidget(self)
        layout = QVBoxLayout(container)

        layout.setSpacing(6)
        layout.setContentsMargins(0, 0, 0, 0)

        help_label = QLabel(help_text)
        help_label.setWordWrap(True)
        help_label.setStyleSheet("color: #c7c1b6; font-size: 11px;")

        layout.addWidget(input_widget)
        layout.addWidget(help_label)

        return container

    def save(self) -> None:
        from ..reviewer import refresh_active_reviewer

        updated = build_settings_config(
            self._raw_config,
            answer_base_values={
                "again": self.again_input.value(),
                "hard": self.hard_input.value(),
                "good": self.good_input.value(),
                "easy": self.easy_input.value(),
            },
            spin_trigger_chance=self.spin_trigger_chance_input.value(),
            spin_trigger_every_n=self.spin_trigger_every_n_input.value(),
        )

        write_addon_config(updated)
        refresh_active_reviewer(suppress_animation=True)
        self.accept()


def show_settings_dialog() -> None:
    SlotMachineSettingsDialog(mw).exec()
