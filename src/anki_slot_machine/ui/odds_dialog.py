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
        summary = config.slot_probability_summary

        summary_lines = [
            "Real 3-reel slot model",
            "Probability-driven multiplier solver",
            (
                "Target expected multiplier: "
                f"{format_decimal(summary.target_expected_multiplier, config.decimal_places)}x"
            ),
            (
                "Achieved expected multiplier: "
                f"{format_decimal(summary.achieved_expected_multiplier, config.decimal_places)}x"
            ),
            (
                "Rarity exponent: "
                f"{format_decimal(summary.rarity_exponent, config.decimal_places)}"
            ),
            (
                "Pair scale multiplier: "
                f"{format_decimal(summary.pair_scale_multiplier, config.decimal_places)}x"
            ),
            (
                "Triple scale multiplier: "
                f"{format_decimal(summary.triple_scale_multiplier, config.decimal_places)}x"
            ),
            f"No-match probability: {_percent(summary.no_match_probability)}",
            f"Any pair probability: {_percent(summary.total_double_probability)}",
            f"Any triple probability: {_percent(summary.total_triple_probability)}",
            (
                "Expected Good payout: "
                f"${format_decimal(summary.expected_good_payout, config.decimal_places)}"
            ),
            (
                "Expected Easy payout: "
                f"${format_decimal(summary.expected_easy_payout, config.decimal_places)}"
            ),
        ]

        odds_lines = []
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
