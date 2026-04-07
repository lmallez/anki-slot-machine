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

from ..service import get_service


class SlotMachineStatsDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent or mw)
        self.setWindowTitle("Slot Machine Stats")
        self.resize(520, 460)

        layout = QVBoxLayout(self)

        self.summary_label = QLabel(self)
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)

        self.history_label = QLabel("Recent spins and losses", self)
        layout.addWidget(self.history_label)

        self.history_view = QPlainTextEdit(self)
        self.history_view.setReadOnly(True)
        layout.addWidget(self.history_view)

        button_row = QHBoxLayout()
        button_row.addStretch(1)

        close_button = QPushButton("Close", self)
        close_button.clicked.connect(self.accept)
        button_row.addWidget(close_button)

        layout.addLayout(button_row)
        self.reload()

    def reload(self) -> None:
        snapshot = get_service().stats_snapshot()
        summary_lines = [
            f"Balance: ${snapshot['balance']}",
            f"Review stake: ${snapshot['review_stake']}",
            f"Total won: ${snapshot['total_won']}",
            f"Total lost: ${snapshot['total_lost']}",
            f"Spins: {snapshot['spins']}",
            f"Current streak: {snapshot['current_streak']}",
            f"Best streak: {snapshot['best_streak']}",
            f"Biggest jackpot: ${snapshot['biggest_jackpot']}",
        ]
        if snapshot["daily_earnings"]:
            summary_lines.append("")
            summary_lines.append("Recent daily earnings:")
            for day, value in snapshot["daily_earnings"]:
                signed_value = value if str(value).startswith("-") else f"+{value}"
                if signed_value.startswith("-"):
                    summary_lines.append(f"{day}: -${signed_value[1:]}")
                else:
                    summary_lines.append(f"{day}: +${signed_value[1:]}")

        history_lines = []
        for event in snapshot["history"]:
            signed_change = (
                event["net_change"]
                if str(event["net_change"]).startswith("-")
                else f"+{event['net_change']}"
            )
            if signed_change.startswith("-"):
                display_change = f"-${signed_change[1:]}"
            else:
                display_change = f"+${signed_change[1:]}"
            history_lines.append(
                f"{event['timestamp'][:19]} | {event['answer_label']:<5} | "
                f"{display_change} | balance ${event['balance_after']}"
            )

        if not history_lines:
            history_lines.append("No spins yet.")

        self.summary_label.setText("\n".join(summary_lines))
        self.history_view.setPlainText("\n".join(history_lines))


def show_stats_dialog() -> None:
    dialog = SlotMachineStatsDialog(parent=mw)
    dialog.exec()
