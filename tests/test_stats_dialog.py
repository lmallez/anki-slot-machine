from __future__ import annotations

import unittest
from unittest.mock import patch

from test_support import install_stubs


class StatsDialogFormattingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        install_stubs()

    def test_history_block_includes_calculation_for_spin_results(self) -> None:
        from anki_slot_machine.ui.stats_dialog import _history_block

        event = {
            "answer_key": "good",
            "answer_label": "Good",
            "timestamp": "2026-04-09T17:51:35+09:00",
            "net_change": "2.50",
            "balance_after": "116.25",
            "did_spin": True,
            "line_hit": True,
            "reels": ["SLOT_1", "SLOT_1", "SLOT_1"],
            "base_reward": "1.00",
            "slot_multiplier": "2.50",
            "matched_symbol": "SLOT_1",
        }

        block = _history_block(event)

        self.assertIn("+$2.50 -> $116.25 · clean hit", block)
        self.assertIn("$1.00 x 2.50 = +$2.50", block)

    def test_history_block_keeps_legacy_events_without_calculation_fields(self) -> None:
        from anki_slot_machine.ui.stats_dialog import _history_block

        event = {
            "answer_key": "good",
            "answer_label": "Good",
            "timestamp": "2026-04-09T17:51:35+09:00",
            "net_change": "2.50",
            "balance_after": "116.25",
            "did_spin": True,
            "line_hit": False,
            "reels": ["SLOT_1", "SLOT_1", "SLOT_3"],
            "matched_symbol": "SLOT_1",
        }

        block = _history_block(event)

        self.assertIn("+$2.50 -> $116.25 · small edge", block)
        self.assertNotIn(" = +$2.50", block)

    def test_history_block_includes_machine_breakdown_for_multi_slot_rounds(self) -> None:
        from anki_slot_machine.ui.stats_dialog import _history_block

        event = {
            "answer_key": "good",
            "answer_label": "Good",
            "timestamp": "2026-04-09T17:51:35+09:00",
            "net_change": "3.45",
            "balance_after": "103.45",
            "did_spin": True,
            "base_reward": "2.00",
            "machine_results": [
                {
                    "machine_key": "alpha",
                    "machine_label": "Alpha",
                    "answer_key": "good",
                    "did_spin": True,
                    "line_hit": True,
                    "reels": ["SLOT_1", "SLOT_1", "SLOT_1"],
                    "base_reward": "1.00",
                    "slot_multiplier": "2.50",
                    "matched_symbol": "SLOT_1",
                    "payout": "2.50",
                    "net_change": "2.50",
                },
                {
                    "machine_key": "beta",
                    "machine_label": "Beta",
                    "answer_key": "good",
                    "did_spin": True,
                    "line_hit": False,
                    "reels": ["SLOT_2", "SLOT_5", "SLOT_2"],
                    "base_reward": "1.00",
                    "slot_multiplier": "0.95",
                    "matched_symbol": "SLOT_2",
                    "payout": "0.95",
                    "net_change": "0.95",
                },
            ],
        }

        block = _history_block(event)

        self.assertIn("+$3.45 -> $103.45 · jackpot spread", block)
        self.assertIn("Alpha: 🐟 🐟 🐟 · clean hit", block)
        self.assertIn("Beta: 🍖 🍀 🍖 · small edge", block)

    def test_reload_does_not_rewrite_history_or_quant_text_when_events_do_not_change(self) -> None:
        from anki_slot_machine.ui import stats_dialog

        snapshot = {
            "balance": "116.25",
            "today_net": "2.50",
            "recent_10": {
                "net": "2.50",
                "hit_count": 1,
                "spin_count": 1,
                "trend_arrow": "↑",
                "trend_label": "accelerating",
            },
            "recent_50": {
                "net": "2.50",
                "hit_count": 1,
                "spin_count": 1,
                "trend_arrow": "↑",
                "trend_label": "accelerating",
            },
            "recent_100": {
                "net": "2.50",
                "hit_count": 1,
                "spin_count": 1,
                "trend_arrow": "↑",
                "trend_label": "accelerating",
            },
            "current_streak": 1,
            "streak_context": "just started",
            "best_streak": 1,
            "spin_win_rate": 100.0,
            "pair_hits": 0,
            "triple_hits": 1,
            "answer_counts": {"again": 0, "hard": 0, "good": 1, "easy": 0},
            "volatility_label": "spiky",
            "average_win": "2.50",
            "average_loss": "0.00",
            "best_win": "2.50",
            "worst_loss": "0.00",
            "biggest_jackpot": "2.50",
            "history_count": 1,
            "lifetime_net": "16.25",
            "session_temperature": "heating up",
            "graph_history": [],
            "history": [
                {
                    "event_id": "evt-1",
                    "answer_key": "good",
                    "answer_label": "Good",
                    "timestamp": "2026-04-09T17:51:35+09:00",
                    "net_change": "2.50",
                    "balance_after": "116.25",
                    "did_spin": True,
                    "line_hit": True,
                    "reels": ["SLOT_1", "SLOT_1", "SLOT_1"],
                    "base_reward": "1.00",
                    "slot_multiplier": "2.50",
                    "matched_symbol": "SLOT_1",
                }
            ],
            "last_result": {
                "event_id": "evt-1",
                "net_change": "2.50",
                "timestamp": "2026-04-09T17:51:35+09:00",
                "answer_key": "good",
                "line_hit": True,
                "matched_symbol": "SLOT_1",
                "payout": "2.50",
            },
        }

        service = type("FakeService", (), {"stats_snapshot": lambda self: snapshot})()

        with patch.object(stats_dialog, "get_service", return_value=service):
            dialog = stats_dialog.SlotMachineStatsDialog()
            initial_history_updates = dialog.history_view._plain_text_updates
            initial_quant_updates = dialog.quant_view._plain_text_updates
            dialog.reload()

        self.assertEqual(dialog.history_view._plain_text_updates, initial_history_updates)
        self.assertEqual(dialog.quant_view._plain_text_updates, initial_quant_updates)

    def test_live_tape_filters_out_non_spin_history_entries(self) -> None:
        from anki_slot_machine.ui import stats_dialog

        snapshot = {
            "balance": "100.00",
            "today_net": "0.00",
            "recent_10": {
                "net": "0.00",
                "hit_count": 0,
                "spin_count": 0,
                "trend_arrow": "→",
                "trend_label": "steady",
            },
            "recent_50": {
                "net": "0.00",
                "hit_count": 0,
                "spin_count": 0,
                "trend_arrow": "→",
                "trend_label": "steady",
            },
            "recent_100": {
                "net": "0.00",
                "hit_count": 0,
                "spin_count": 0,
                "trend_arrow": "→",
                "trend_label": "steady",
            },
            "current_streak": 0,
            "streak_context": "cooled off",
            "best_streak": 1,
            "spin_win_rate": 0.0,
            "pair_hits": 0,
            "triple_hits": 0,
            "answer_counts": {"again": 0, "hard": 1, "good": 1, "easy": 0},
            "volatility_label": "quiet",
            "average_win": "0.00",
            "average_loss": "0.00",
            "best_win": "0.00",
            "worst_loss": "0.00",
            "biggest_jackpot": "0.00",
            "history_count": 2,
            "lifetime_net": "0.00",
            "session_temperature": "holding steady",
            "graph_history": [],
            "history": [
                {
                    "event_id": "evt-spin",
                    "answer_key": "good",
                    "answer_label": "Good",
                    "timestamp": "2026-04-09T17:51:35+09:00",
                    "net_change": "2.50",
                    "balance_after": "102.50",
                    "did_spin": True,
                    "line_hit": True,
                    "reels": ["SLOT_1", "SLOT_1", "SLOT_1"],
                    "base_reward": "1.00",
                    "slot_multiplier": "2.50",
                    "matched_symbol": "SLOT_1",
                },
                {
                    "event_id": "evt-stack",
                    "answer_key": "hard",
                    "answer_label": "Hard",
                    "timestamp": "2026-04-09T17:52:35+09:00",
                    "net_change": "0.00",
                    "balance_after": "102.50",
                    "did_spin": False,
                    "no_spin": True,
                    "base_reward": "0.50",
                    "stack_value": "1.50",
                },
            ],
            "last_result": {
                "event_id": "evt-spin",
                "net_change": "2.50",
                "timestamp": "2026-04-09T17:51:35+09:00",
                "answer_key": "good",
                "line_hit": True,
                "matched_symbol": "SLOT_1",
                "payout": "2.50",
            },
        }

        service = type("FakeService", (), {"stats_snapshot": lambda self: snapshot})()

        with patch.object(stats_dialog, "get_service", return_value=service):
            dialog = stats_dialog.SlotMachineStatsDialog()

        history_text = dialog.history_view._text
        self.assertIn("+$2.50 -> $102.50 · clean hit", history_text)
        self.assertNotIn("evt-stack", history_text)
        self.assertNotIn("[Hard]", history_text)


if __name__ == "__main__":
    unittest.main()
