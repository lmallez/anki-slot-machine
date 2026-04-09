from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from aqt import mw
from aqt.qt import (
    QColor,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPainter,
    QPen,
    QPlainTextEdit,
    QPushButton,
    QTimer,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from ..service import get_service


SYMBOL_EMOJIS = {
    "SLOT_1": "🐟",
    "SLOT_2": "🍖",
    "SLOT_3": "🔑",
    "SLOT_4": "👑",
    "SLOT_5": "🍀",
}
_active_dialog: SlotMachineStatsDialog | None = None


def _reel_emoji_strip(event: dict) -> str:
    if not event.get("did_spin"):
        return "— — —"
    reels = event.get("reels") or []
    mapped = [SYMBOL_EMOJIS.get(str(symbol), "⬛") for symbol in reels[:3]]
    if not mapped:
        return "⬛ ⬛ ⬛"
    return " ".join(mapped)


def _signed_money(value: str) -> str:
    text = str(value)
    if text.startswith("-"):
        return f"-${text[1:]}"
    return f"+${text}"


def _tone_for_money(value: str) -> str:
    text = str(value)
    if text.startswith("-"):
        return "negative"
    if text in {"0", "0.0", "0.00"}:
        return "neutral"
    return "positive"


def _money_color(value: str) -> str:
    tone = _tone_for_money(value)
    if tone == "negative":
        return "#d35b56"
    if tone == "positive":
        return "#5fc86f"
    return "#f2f2ed"


def _human_timestamp(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return raw[:19]
    return parsed.strftime("%H:%M:%S")


def _relative_timestamp(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "waiting"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return "recently"
    now = datetime.now().astimezone()
    delta = now - parsed.astimezone(now.tzinfo)
    seconds = max(0, int(delta.total_seconds()))
    if seconds < 10:
        return "just now"
    if seconds < 60:
        return f"{seconds}s ago"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h ago"
    days = hours // 24
    return f"{days}d ago"


def _summary_sentence(summary: dict) -> str:
    review_count = int(summary.get("review_count", 0))
    if review_count <= 0:
        return "No recent prints."

    spin_count = int(summary.get("spin_count", 0))
    if spin_count > 0:
        hit_text = (
            f"{summary.get('hit_count', 0)}/{spin_count} hits "
            f"({summary.get('hit_rate', 0)}%)"
        )
    else:
        hit_text = "no spins"

    return (
        f"{summary.get('label', 'Recent')}: {_signed_money(str(summary.get('net', '0')))}"
        f" • {hit_text} • avg win ${summary.get('average_win', '0')}"
    )


def _trade_commentary(event: dict) -> str:
    answer = str(event.get("answer_key", ""))
    matched = bool(event.get("matched_symbol"))
    triple = bool(event.get("line_hit"))
    payout_text = str(event.get("payout", "0"))

    if answer == "hard":
        return "holds"
    if answer == "again":
        if triple:
            return "full liquidation"
        if matched:
            return "caught the downside"
        return "bleeds quietly"
    if triple and answer == "easy":
        return "leverage paid"
    if triple:
        return "clean hit"
    if matched:
        return "small edge"
    if payout_text in {"0", "0.0", "0.00"}:
        return "dead spin"
    if answer == "easy":
        return "risk on"
    return "prints green"


def _calculation_strip(event: dict) -> str:
    answer = str(event.get("answer_key", ""))
    if answer == "hard":
        return ""

    raw_base = event.get("base_reward")
    raw_multiplier = event.get("slot_multiplier")
    raw_change = event.get("net_change")
    if raw_base is None or raw_multiplier is None or raw_change is None:
        return ""

    base = str(raw_base)
    multiplier = str(raw_multiplier)
    change = _signed_money(str(raw_change))
    if answer == "again":
        return f"-${base} x {multiplier} = {change}"
    return f"${base} x {multiplier} = {change}"


def _history_block(event: dict) -> str:
    answer = str(event.get("answer_label", "Roll"))
    change = _signed_money(str(event.get("net_change", "0")))
    balance = f"${event.get('balance_after', '0')}"
    commentary = _trade_commentary(event)
    timestamp = _human_timestamp(str(event.get("timestamp", "")))
    recency = _relative_timestamp(str(event.get("timestamp", "")))
    reels = _reel_emoji_strip(event)
    calculation = _calculation_strip(event)
    details = f"{timestamp} · {recency} · {reels}"
    if calculation:
        details = f"{details} · {calculation}"
    return (
        f"[{answer}] {change} -> {balance} · {commentary}\n"
        f"{details}"
    )


def _history_signature(events: list[dict]) -> tuple[tuple[str, str, str, str, str, str], ...]:
    return tuple(
        (
            str(event.get("event_id", "")),
            str(event.get("timestamp", "")),
            str(event.get("card_id", "")),
            str(event.get("net_change", "")),
            str(event.get("balance_after", "")),
            str(event.get("matched_symbol", "")),
        )
        for event in events
    )


def _market_state(snapshot: dict) -> str:
    recent = snapshot.get("recent_10", {})
    today_net = _signed_money(str(snapshot.get("today_net", "0")))
    return (
        f"{str(snapshot.get('session_temperature', 'holding steady')).title()} · "
        f"{today_net} today · momentum {recent.get('trend_arrow', '→')}"
    )


def _quant_panel_text(snapshot: dict) -> str:
    recent_10 = snapshot.get("recent_10", {})
    recent_50 = snapshot.get("recent_50", {})
    recent_100 = snapshot.get("recent_100", {})
    answer_counts = snapshot.get("answer_counts", {})

    return "\n".join(
        [
            "QUANT SIDEBAR // FOR NERDS ONLY",
            "",
            "WINDOWS",
            (
                f"Last 10   {_signed_money(str(recent_10.get('net', '0'))):>9}   "
                f"{recent_10.get('hit_count', 0)}/{recent_10.get('spin_count', 0)} hits   "
                f"{recent_10.get('trend_arrow', '→')} {recent_10.get('trend_label', 'steady')}"
            ),
            (
                f"Last 50   {_signed_money(str(recent_50.get('net', '0'))):>9}   "
                f"{recent_50.get('hit_count', 0)}/{recent_50.get('spin_count', 0)} hits   "
                f"{recent_50.get('trend_arrow', '→')} {recent_50.get('trend_label', 'steady')}"
            ),
            (
                f"Last 100  {_signed_money(str(recent_100.get('net', '0'))):>9}   "
                f"{recent_100.get('hit_count', 0)}/{recent_100.get('spin_count', 0)} hits   "
                f"{recent_100.get('trend_arrow', '→')} {recent_100.get('trend_label', 'steady')}"
            ),
            "",
            "FLOW",
            f"Current streak   {snapshot.get('current_streak', 0)} ({snapshot.get('streak_context', 'steady')})",
            f"Best streak      {snapshot.get('best_streak', 0)}",
            f"Spin win rate    {snapshot.get('spin_win_rate', 0)}%",
            f"Pairs / triples  {snapshot.get('pair_hits', 0)} / {snapshot.get('triple_hits', 0)}",
            "",
            "VARIANCE",
            f"Volatility       {str(snapshot.get('volatility_label', 'balanced')).title()}",
            f"Avg win / loss   ${snapshot.get('average_win', '0')} / ${snapshot.get('average_loss', '0')}",
            f"Best / worst     ${snapshot.get('best_win', '0')} / ${snapshot.get('worst_loss', '0')}",
            f"Jackpot          ${snapshot.get('biggest_jackpot', '0')}",
            "",
            "ORDER FLOW",
            f"Again            {answer_counts.get('again', 0)}",
            f"Hard             {answer_counts.get('hard', 0)}",
            f"Good             {answer_counts.get('good', 0)}",
            f"Easy             {answer_counts.get('easy', 0)}",
            "",
            "TRACKED",
            f"Reviews          {snapshot.get('history_count', 0)}",
            f"Lifetime net     {_signed_money(str(snapshot.get('lifetime_net', '0')))}",
        ]
    )


class RollHistoryGraph(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._values: list[float] = []
        self._events: list[dict] = []
        self._latest_value = 0.0
        self._high_value = 0.0
        self._low_value = 0.0
        self._hover_index: int | None = None
        self._pulse_last_point = False
        self.setMinimumHeight(380)
        self.setMouseTracking(True)

    def _plot_metrics(self) -> tuple[int, int, int, int, int, int]:
        width = max(1, self.width())
        height = max(1, self.height())
        margin_left = 18
        margin_right = 16
        margin_top = 18
        margin_bottom = 26
        plot_width = max(1, width - margin_left - margin_right)
        plot_height = max(1, height - margin_top - margin_bottom)
        plot_left = margin_left
        plot_top = margin_top
        plot_bottom = plot_top + plot_height
        return width, height, plot_left, plot_top, plot_width, plot_bottom

    def set_roll_history(self, events: list[dict]) -> None:
        running_total = Decimal("0")
        values: list[float] = []
        for event in events:
            running_total += Decimal(str(event.get("net_change", "0")))
            values.append(float(running_total))
        self._events = list(events)
        self._values = values
        self._latest_value = values[-1] if values else 0.0
        self._high_value = max(values) if values else 0.0
        self._low_value = min(values) if values else 0.0
        self._hover_index = None
        self.update()

    def _plot_points(self) -> list[tuple[int, int]]:
        if not self._values:
            return []

        _width, _height, plot_left, plot_top, plot_width, plot_bottom = self._plot_metrics()
        plot_height = plot_bottom - plot_top

        min_value = min(min(self._values), 0.0)
        max_value = max(max(self._values), 0.0)
        if max_value == min_value:
            max_value += 1.0
            min_value -= 1.0
        spread = max_value - min_value

        def y_for(value: float) -> int:
            ratio = (value - min_value) / spread
            return int(round(plot_bottom - ratio * plot_height))

        if len(self._values) == 1:
            return [(plot_left, y_for(self._values[0]))]

        last_index = len(self._values) - 1
        return [
            (
                plot_left + int(round((index / last_index) * plot_width)),
                y_for(value),
            )
            for index, value in enumerate(self._values)
        ]

    def mouseMoveEvent(self, event) -> None:  # pragma: no cover - GUI hover
        if not self._events:
            QToolTip.hideText()
            return

        _width, _height, plot_left, plot_top, plot_width, plot_bottom = self._plot_metrics()
        x_pos = (
            event.position().x()
            if hasattr(event, "position")
            else event.pos().x()
        )
        y_pos = (
            event.position().y()
            if hasattr(event, "position")
            else event.pos().y()
        )
        if (
            x_pos < plot_left
            or x_pos > plot_left + plot_width
            or y_pos < plot_top
            or y_pos > plot_bottom
        ):
            if self._hover_index is not None:
                self._hover_index = None
                self.update()
            QToolTip.hideText()
            return

        points = self._plot_points()
        index = min(
            range(len(points)),
            key=lambda idx: abs(points[idx][0] - x_pos) + abs(points[idx][1] - y_pos) * 0.35,
        )
        if self._hover_index != index:
            self._hover_index = index
            self.update()
        event_payload = self._events[index]
        tooltip_lines = [
            f"{_human_timestamp(str(event_payload.get('timestamp', '')))} · {_relative_timestamp(str(event_payload.get('timestamp', '')))}",
            f"{_history_block(event_payload)}",
        ]
        global_point = (
            event.globalPosition().toPoint()
            if hasattr(event, "globalPosition")
            else event.globalPos()
        )
        QToolTip.showText(global_point, "\n".join(tooltip_lines), self)

    def leaveEvent(self, _event) -> None:  # pragma: no cover - GUI hover
        self._hover_index = None
        self.update()
        QToolTip.hideText()

    def paintEvent(self, _event) -> None:  # pragma: no cover - GUI paint
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        width, height, plot_left, plot_top, plot_width, plot_bottom = self._plot_metrics()
        plot_height = plot_bottom - plot_top

        painter.fillRect(0, 0, width, height, QColor("#101010"))
        painter.setPen(QPen(QColor("#3a2b16"), 1))
        painter.drawRect(0, 0, width - 1, height - 1)

        if not self._values:
            painter.setPen(QPen(QColor("#f2f2ed"), 1))
            painter.drawText(
                plot_left,
                plot_top,
                plot_width,
                plot_height,
                0,
                "No prints yet.",
            )
            return

        min_value = min(min(self._values), 0.0)
        max_value = max(max(self._values), 0.0)
        if max_value == min_value:
            max_value += 1.0
            min_value -= 1.0
        spread = max_value - min_value

        def y_for(value: float) -> int:
            ratio = (value - min_value) / spread
            return int(round(plot_bottom - ratio * plot_height))

        zero_y = y_for(0.0)
        painter.setPen(QPen(QColor("#3a2b16"), 1))
        painter.drawLine(plot_left, zero_y, plot_left + plot_width, zero_y)

        line_color = "#5fc86f" if self._latest_value >= 0 else "#d35b56"
        glow_color = "#2e8a3d" if self._latest_value >= 0 else "#6f1d1e"
        points = self._plot_points()

        if len(points) > 1:
            painter.setPen(QPen(QColor(glow_color), 5))
            last_x, last_y = points[0]
            for x, y in points[1:]:
                painter.drawLine(last_x, last_y, x, y)
                last_x, last_y = x, y

        painter.setPen(QPen(QColor(line_color), 2))
        last_x, last_y = points[0]
        for x, y in points[1:]:
            painter.drawLine(last_x, last_y, x, y)
            last_x, last_y = x, y

        if self._hover_index is not None and 0 <= self._hover_index < len(points):
            hover_x, hover_y = points[self._hover_index]
            painter.setPen(QPen(QColor("#c9c2b4"), 1))
            painter.drawLine(hover_x, plot_top, hover_x, plot_bottom)
            painter.setPen(QPen(QColor(line_color), 1))
            painter.setBrush(QColor("#f2f2ed"))
            painter.drawEllipse(hover_x - 4, hover_y - 4, 8, 8)

        last_x, last_y = points[-1]
        if self._pulse_last_point:
            painter.setPen(QPen(QColor(glow_color), 1))
            painter.setBrush(QColor(glow_color))
            painter.drawEllipse(last_x - 8, last_y - 8, 16, 16)
        painter.setPen(QPen(QColor(line_color), 1))
        painter.setBrush(QColor("#f2f2ed"))
        painter.drawEllipse(last_x - 4, last_y - 4, 8, 8)

        painter.setPen(QPen(QColor("#f2f2ed"), 1))
        painter.drawText(plot_left, plot_top + 14, f"HIGH {self._high_value:+.2f}")
        painter.drawText(plot_left + plot_width - 92, plot_top + 14, f"NOW {self._latest_value:+.2f}")
        painter.drawText(plot_left, plot_bottom + 18, f"LOW  {self._low_value:+.2f}")

    def pulse_last_point(self) -> None:
        self._pulse_last_point = True
        self.update()
        QTimer.singleShot(450, self._clear_last_point_pulse)

    def _clear_last_point_pulse(self) -> None:
        self._pulse_last_point = False
        self.update()


class SlotMachineStatsDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent or mw)
        self.setWindowTitle("Slot Terminal")
        self.resize(1080, 860)
        self._last_event_id: str | None = None
        self._plain_text_signatures: dict[str, object] = {}
        self.setStyleSheet(
            """
            QDialog {
                background: #121212;
                color: #f2f2ed;
            }
            QLabel {
                color: #f2f2ed;
            }
            QPushButton {
                background: #1b1b1b;
                color: #f2f2ed;
                border: 1px solid #3a2b16;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background: #242424;
            }
            """
        )

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        self.signal_bar = QFrame(self)
        self.signal_bar.setStyleSheet(
            """
            QFrame {
                background: #101010;
                border: 1px solid #3a2b16;
                border-radius: 10px;
            }
            QLabel {
                background: transparent;
                border: 0;
            }
            """
        )
        signal_layout = QHBoxLayout(self.signal_bar)
        signal_layout.setContentsMargins(14, 12, 14, 12)
        signal_layout.setSpacing(16)

        self.balance_label = QLabel(self.signal_bar)
        self.last_print_label = QLabel(self.signal_bar)
        self.market_state_label = QLabel(self.signal_bar)
        self.balance_label.setWordWrap(True)
        self.last_print_label.setWordWrap(True)
        self.market_state_label.setWordWrap(True)

        signal_layout.addWidget(self.balance_label, 2)
        signal_layout.addWidget(self.last_print_label, 2)
        signal_layout.addWidget(self.market_state_label, 3)
        layout.addWidget(self.signal_bar)

        content_row = QHBoxLayout()
        content_row.setSpacing(10)

        left_column = QVBoxLayout()
        left_column.setSpacing(10)

        self.chart_frame = QFrame(self)
        self.chart_frame.setStyleSheet(
            """
            QFrame {
                background: #101010;
                border: 1px solid #3a2b16;
                border-radius: 12px;
            }
            QLabel {
                background: transparent;
                border: 0;
            }
            """
        )
        chart_layout = QVBoxLayout(self.chart_frame)
        chart_layout.setContentsMargins(6, 4, 6, 6)
        chart_layout.setSpacing(2)

        self.chart_header = QLabel(self.chart_frame)
        self.chart_header.setWordWrap(True)
        self.graph_view = RollHistoryGraph(self.chart_frame)
        chart_layout.addWidget(self.chart_header)
        chart_layout.addWidget(self.graph_view)
        left_column.addWidget(self.chart_frame, 3)

        self.feed_frame = QFrame(self)
        self.feed_frame.setStyleSheet(
            """
            QFrame {
                background: #101010;
                border: 1px solid #3a2b16;
                border-radius: 12px;
            }
            QLabel {
                background: transparent;
                border: 0;
            }
            QPlainTextEdit {
                background: #101010;
                color: #f2f2ed;
                border: 0;
                padding: 8px 10px 10px;
                font-family: Menlo, Monaco, 'Courier New', monospace;
                font-size: 15px;
                selection-background-color: #6f1d1e;
            }
            """
        )
        feed_layout = QVBoxLayout(self.feed_frame)
        feed_layout.setContentsMargins(12, 10, 12, 12)
        feed_layout.setSpacing(6)
        self.feed_header = QLabel(self.feed_frame)
        self.feed_header.setWordWrap(True)
        self.history_view = QPlainTextEdit(self.feed_frame)
        self.history_view.setReadOnly(True)
        feed_layout.addWidget(self.feed_header)
        feed_layout.addWidget(self.history_view)
        left_column.addWidget(self.feed_frame, 2)

        self.quant_frame = QFrame(self)
        self.quant_frame.setStyleSheet(
            """
            QFrame {
                background: #0f0f0f;
                border: 1px solid #2f2315;
                border-radius: 12px;
            }
            QLabel {
                background: transparent;
                border: 0;
                color: #9f9787;
            }
            QPlainTextEdit {
                background: #0f0f0f;
                color: #8f8578;
                border: 0;
                padding: 6px 8px 8px;
                font-family: Menlo, Monaco, 'Courier New', monospace;
                font-size: 10px;
                selection-background-color: #6f1d1e;
            }
            """
        )
        quant_layout = QVBoxLayout(self.quant_frame)
        quant_layout.setContentsMargins(12, 10, 12, 12)
        quant_layout.setSpacing(6)
        self.quant_header = QLabel(self.quant_frame)
        self.quant_header.setWordWrap(True)
        self.quant_view = QPlainTextEdit(self.quant_frame)
        self.quant_view.setReadOnly(True)
        quant_layout.addWidget(self.quant_header)
        quant_layout.addWidget(self.quant_view)

        content_row.addLayout(left_column, 5)
        content_row.addWidget(self.quant_frame, 2)
        layout.addLayout(content_row)

        button_row = QHBoxLayout()
        button_row.addStretch(1)

        refresh_button = QPushButton("Refresh", self)
        refresh_button.clicked.connect(self.reload)
        button_row.addWidget(refresh_button)

        close_button = QPushButton("Close", self)
        close_button.clicked.connect(self.close)
        button_row.addWidget(close_button)

        layout.addLayout(button_row)

        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(1200)
        self._refresh_timer.timeout.connect(self.reload)
        self._refresh_timer.start()
        self.reload()

    def closeEvent(self, event) -> None:  # pragma: no cover - GUI lifecycle
        global _active_dialog
        _active_dialog = None
        super().closeEvent(event)

    def _flash_frame(self, frame: QFrame, border: str) -> None:
        frame.setStyleSheet(
            f"""
            QFrame {{
                background: #17120f;
                border: 1px solid {border};
                border-radius: 12px;
            }}
            QLabel {{
                background: transparent;
                border: 0;
                color: #f2f2ed;
            }}
            """
        )

    def _clear_frame_flash(self) -> None:
        self.signal_bar.setStyleSheet(
            """
            QFrame {
                background: #101010;
                border: 1px solid #3a2b16;
                border-radius: 10px;
            }
            QLabel {
                background: transparent;
                border: 0;
            }
            """
        )
        self.chart_frame.setStyleSheet(
            """
            QFrame {
                background: #101010;
                border: 1px solid #3a2b16;
                border-radius: 12px;
            }
            QLabel {
                background: transparent;
                border: 0;
            }
            """
        )
        self.feed_frame.setStyleSheet(
            """
            QFrame {
                background: #101010;
                border: 1px solid #3a2b16;
                border-radius: 12px;
            }
            QLabel {
                background: transparent;
                border: 0;
            }
            QPlainTextEdit {
                background: #101010;
                color: #f2f2ed;
                border: 0;
                padding: 8px 10px 10px;
                font-family: Menlo, Monaco, 'Courier New', monospace;
                font-size: 15px;
                selection-background-color: #6f1d1e;
            }
            """
        )

    def _flash_live_surfaces(self, snapshot: dict) -> None:
        tone = _tone_for_money(str((snapshot.get("last_result") or {}).get("net_change", "0")))
        border = "#2e8a3d" if tone == "positive" else "#6f1d1e" if tone == "negative" else "#8f6825"
        self._flash_frame(self.signal_bar, border)
        self._flash_frame(self.chart_frame, border)
        self._flash_frame(self.feed_frame, border)
        QTimer.singleShot(650, self._clear_frame_flash)

    def _set_cached_plain_text(
        self,
        *,
        cache_key: str,
        signature: object,
        widget: QPlainTextEdit,
        text: str,
    ) -> None:
        if self._plain_text_signatures.get(cache_key) == signature:
            return
        widget.setPlainText(text)
        self._plain_text_signatures[cache_key] = signature

    def reload(self) -> None:
        snapshot = get_service().stats_snapshot()
        last_result = snapshot.get("last_result") or {}
        last_event_id = str(last_result.get("event_id", "")).strip() or None
        had_previous_event = self._last_event_id is not None
        event_changed = bool(
            last_event_id and had_previous_event and last_event_id != self._last_event_id
        )

        balance_color = _money_color(str(snapshot.get("today_net", "0")))
        last_print_color = _money_color(str(last_result.get("net_change", "0")))

        self.balance_label.setText(
            "<div style='color:#c9c2b4; font-size:10px; letter-spacing:0.08em;'>BALANCE</div>"
            f"<div style='font-size:28px; font-weight:700; color:{balance_color};'>${snapshot.get('balance', '0')}</div>"
        )

        if last_result:
            last_print_text = _signed_money(str(last_result.get("net_change", "0")))
            last_print_detail = _trade_commentary(last_result)
            recency = _relative_timestamp(str(last_result.get("timestamp", "")))
        else:
            last_print_text = "$0.00"
            last_print_detail = "waiting for the next print"
            recency = "idle"

        self.last_print_label.setText(
            "<div style='color:#c9c2b4; font-size:10px; letter-spacing:0.08em;'>LAST PRINT</div>"
            f"<div style='font-size:24px; font-weight:700; color:{last_print_color};'>{last_print_text}</div>"
            f"<div style='color:#c9c2b4; font-size:12px;'>{last_print_detail} · {recency}</div>"
        )

        self.market_state_label.setText(
            "<div style='color:#c9c2b4; font-size:10px; letter-spacing:0.08em;'>MARKET STATE</div>"
            f"<div style='font-size:18px; font-weight:700;'>{_market_state(snapshot)}</div>"
        )

        self.chart_header.setText("")
        self.chart_header.setVisible(False)
        self.graph_view.set_roll_history(snapshot.get("graph_history", []))

        self.feed_header.setText(
            "<div style='font-size:13px; font-weight:700; color:#f2f2ed;'>LIVE TAPE</div>"
            "<div style='color:#c9c2b4; font-size:11px;'>Newest first. Short, punchy, mildly overconfident.</div>"
        )
        history_events = snapshot.get("history", [])
        history_signature = _history_signature(history_events)
        history_lines = [_history_block(event) for event in history_events]
        if not history_lines:
            history_lines.append("No prints yet.")
        self._set_cached_plain_text(
            cache_key="history",
            signature=history_signature,
            widget=self.history_view,
            text="\n".join(history_lines),
        )

        self.quant_header.setText(
            "<div style='font-size:12px; font-weight:700; color:#9f9787;'>QUANT SIDEBAR</div>"
            "<div style='color:#7f7567; font-size:10px;'>Dense, dimmed, and intentionally excessive.</div>"
        )
        quant_text = _quant_panel_text(snapshot)
        self._set_cached_plain_text(
            cache_key="quant",
            signature=quant_text,
            widget=self.quant_view,
            text=quant_text,
        )

        if event_changed:
            self._flash_live_surfaces(snapshot)
            self.graph_view.pulse_last_point()
        self._last_event_id = last_event_id


def show_stats_dialog() -> None:
    global _active_dialog

    if _active_dialog is not None:
        _active_dialog.reload()
        _active_dialog.showNormal()
        _active_dialog.raise_()
        _active_dialog.activateWindow()
        return

    dialog = SlotMachineStatsDialog(parent=mw)
    _active_dialog = dialog
    dialog.show()
    dialog.raise_()
    dialog.activateWindow()
