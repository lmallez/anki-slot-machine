from __future__ import annotations

from aqt import mw
from aqt.qt import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from ..decimal_utils import format_decimal
from ..service import get_service


def _percent(value: float) -> str:
    return f"{value * 100:.2f}%"


class SlotMachineOddsDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent or mw)
        self.setWindowTitle("Slot Machine Odds")
        self.resize(560, 500)

        layout = QVBoxLayout(self)

        self.summary_label = QLabel(self)
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)

        self.odds_label = QLabel("Symbol probabilities and rewards", self)
        layout.addWidget(self.odds_label)

        self.odds_view = QPlainTextEdit(self)
        self.odds_view.setReadOnly(True)
        layout.addWidget(self.odds_view)

        button_row = QHBoxLayout()
        button_row.addStretch(1)

        close_button = QPushButton("Close", self)
        close_button.clicked.connect(self.accept)
        button_row.addWidget(close_button)

        layout.addLayout(button_row)
        self.reload()

    def reload(self) -> None:
        config = get_service().config()
        machine_count = len(config.machines)
        aggregate_good = sum(
            (
                machine.slot_probability_summary.expected_good_payout
                for machine in config.machines
            )
        )
        aggregate_easy = sum(
            (
                machine.slot_probability_summary.expected_easy_payout
                for machine in config.machines
            )
        )

        summary_lines = [
            f"Real 3-reel slot model across {machine_count} machine(s)",
            f"Shared profile: {config.slot_probability_summary.profile_name}",
            f"Profile file: {config.slot_probability_summary.profile_path}",
            (
                "Configured answer values: "
                f"Again {format_decimal(config.answer_base_values['again'], config.decimal_places)}, "
                f"Hard {format_decimal(config.answer_base_values['hard'], config.decimal_places)}, "
                f"Good {format_decimal(config.answer_base_values['good'], config.decimal_places)}, "
                f"Easy {format_decimal(config.answer_base_values['easy'], config.decimal_places)}"
            ),
            (
                "Aggregate expected Good payout per settled machine spin: "
                f"${format_decimal(aggregate_good, config.decimal_places)}"
            ),
            (
                "Aggregate expected Easy payout per settled machine spin: "
                f"${format_decimal(aggregate_easy, config.decimal_places)}"
            ),
            (
                "Spin trigger: all answers build one shared stack; the Nth review settles "
                "that stack and may turn the settlement into a spin."
            ),
            (
                "Roll cost: "
                f"${format_decimal(config.roll_cost, config.decimal_places)} per visible machine "
                "on each review, tracked separately from the shared stack and "
                "not included in the odds table."
            ),
        ]

        odds_lines = []
        summary = config.slot_probability_summary
        odds_lines.extend(
            [
                "Shared machine configuration",
                (
                    "Expected multiplier per machine spin: "
                    f"{format_decimal(summary.expected_multiplier, config.decimal_places)}x"
                ),
                f"No-match probability: {_percent(summary.no_match_probability)}",
                f"Any pair probability: {_percent(summary.total_double_probability)}",
                f"Any triple probability: {_percent(summary.total_triple_probability)}",
                f"Any hit probability: {_percent(summary.hit_probability)}",
                (
                    "Expected Again payout per settled machine spin: "
                    f"${format_decimal(summary.expected_again_payout, config.decimal_places)}"
                ),
                (
                    "Expected Hard payout per settled machine spin: "
                    f"${format_decimal(summary.expected_hard_payout, config.decimal_places)}"
                ),
                (
                    "Expected Good payout per settled machine spin: "
                    f"${format_decimal(summary.expected_good_payout, config.decimal_places)}"
                ),
                (
                    "Expected Easy payout per settled machine spin: "
                    f"${format_decimal(summary.expected_easy_payout, config.decimal_places)}"
                ),
                "",
            ]
        )
        odds_lines.extend(
            [
                "Active windows",
                *[f"- {machine.label} [{machine.key}]" for machine in config.machines],
                "",
            ]
        )
        for odds in summary.symbol_odds:
            odds_lines.extend(
                [
                    f"{odds.symbol} ({odds.faces} faces)",
                    f"  Reel probability: {_percent(odds.single_probability)}",
                    (
                        f"  Exact pair: {_percent(odds.double_probability)}"
                        f" -> x{format_decimal(odds.double_multiplier, config.decimal_places)}"
                    ),
                    (
                        f"  Triple: {_percent(odds.triple_probability)}"
                        f" -> x{format_decimal(odds.triple_multiplier, config.decimal_places)}"
                    ),
                    "",
                ]
            )

        if odds_lines:
            odds_lines.pop()

        self.summary_label.setText("\n".join(summary_lines))
        self.odds_view.setPlainText("\n".join(odds_lines))


def show_odds_dialog() -> None:
    dialog = SlotMachineOddsDialog(parent=mw)
    dialog.exec()
