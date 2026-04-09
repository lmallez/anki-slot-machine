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

        self.assertIn("[Good] +$2.50 -> $116.25 · clean hit", block)
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

        self.assertIn("[Good] +$2.50 -> $116.25 · small edge", block)
        self.assertNotIn(" = +$2.50", block)

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


if __name__ == "__main__":
    unittest.main()
