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

    def test_history_block_uses_per_spin_roll_cost_instead_of_pending_window_cost(self) -> None:
        from anki_slot_machine.ui.stats_dialog import _history_block

        event = {
            "answer_key": "good",
            "answer_label": "Good",
            "timestamp": "2026-04-09T17:51:35+09:00",
            "net_change": "1.85",
            "balance_after": "99.85",
            "did_spin": True,
            "line_hit": False,
            "reels": ["SLOT_2", "SLOT_5", "SLOT_2"],
            "base_reward": "3.00",
            "stack_value": "3.00",
            "slot_multiplier": "0.95",
            "matched_symbol": "SLOT_2",
            "payout": "2.85",
            "roll_cost": "1.00",
            "pending_roll_cost": "3.00",
        }

        block = _history_block(event)

        self.assertIn("+$1.85 -> $99.85 · small edge", block)
        self.assertIn("result +$2.85 · roll cost $1.00 · net +$1.85", block)
        self.assertNotIn("roll cost $3.00", block)
        self.assertNotIn("net -$0.15", block)

    def test_history_block_uses_machine_pending_roll_cost_for_multi_machine_spin_lines(self) -> None:
        from anki_slot_machine.ui.stats_dialog import _history_block

        event = {
            "event_id": "evt-multi-stack",
            "timestamp": "2026-04-09T17:51:35+09:00",
            "answer_key": "good",
            "answer_label": "Good",
            "net_change": "8.35",
            "balance_after": "108.35",
            "did_spin": True,
            "line_hit": False,
            "reels": ["MISS", "MISS", "MISS"],
            "base_reward": "6.00",
            "payout": "10.35",
            "roll_cost": "2.00",
            "pending_roll_cost": "6.00",
            "machine_results": [
                {
                    "machine_key": "alpha",
                    "machine_label": "Alpha",
                    "timestamp": "2026-04-09T17:51:35+09:00",
                    "answer_key": "good",
                    "did_spin": True,
                    "line_hit": True,
                    "reels": ["SLOT_1", "SLOT_1", "SLOT_1"],
                    "base_reward": "3.00",
                    "payout": "7.50",
                    "roll_cost": "1.00",
                    "pending_roll_cost": "3.00",
                    "slot_multiplier": "2.50",
                    "net_change": "6.50",
                    "balance_after": "104.50",
                    "matched_symbol": "SLOT_1",
                },
                {
                    "machine_key": "beta",
                    "machine_label": "Beta",
                    "timestamp": "2026-04-09T17:51:35+09:00",
                    "answer_key": "good",
                    "did_spin": True,
                    "line_hit": False,
                    "reels": ["SLOT_2", "SLOT_5", "SLOT_2"],
                    "base_reward": "3.00",
                    "payout": "2.85",
                    "roll_cost": "1.00",
                    "pending_roll_cost": "3.00",
                    "slot_multiplier": "0.95",
                    "net_change": "1.85",
                    "balance_after": "108.35",
                    "matched_symbol": "SLOT_2",
                },
            ],
        }

        block = _history_block(event)

        self.assertIn("Alpha: 🐟 🐟 🐟 · clean hit · result +$7.50 · roll cost $3.00 · net +$4.50", block)
        self.assertIn("Beta: 🍖 🍀 🍖 · small edge · result +$2.85 · roll cost $3.00 · net -$0.15", block)

    def test_reload_does_not_rewrite_history_or_quant_text_when_events_do_not_change(self) -> None:
        from anki_slot_machine.ui import stats_dialog

        snapshot = {
            "balance": "116.25",
            "today_net": "2.50",
            "recent_10": {
                "net": "2.50",
                "roll_cost": "1.00",
                "hit_count": 1,
                "spin_count": 1,
                "trend_arrow": "↑",
                "trend_label": "accelerating",
            },
            "recent_50": {
                "net": "2.50",
                "roll_cost": "1.00",
                "hit_count": 1,
                "spin_count": 1,
                "trend_arrow": "↑",
                "trend_label": "accelerating",
            },
            "recent_100": {
                "net": "2.50",
                "roll_cost": "1.00",
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
            "lifetime_roll_cost": "3.00",
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
                "roll_cost": "0.00",
                "hit_count": 0,
                "spin_count": 0,
                "trend_arrow": "→",
                "trend_label": "steady",
            },
            "recent_50": {
                "net": "0.00",
                "roll_cost": "0.00",
                "hit_count": 0,
                "spin_count": 0,
                "trend_arrow": "→",
                "trend_label": "steady",
            },
            "recent_100": {
                "net": "0.00",
                "roll_cost": "0.00",
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
            "lifetime_roll_cost": "0.00",
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

    def test_summary_sentence_mentions_roll_flow(self) -> None:
        from anki_slot_machine.ui.stats_dialog import _summary_sentence

        summary = {
            "label": "Last 10",
            "review_count": 10,
            "spin_count": 4,
            "hit_count": 2,
            "hit_rate": 50.0,
            "net": "3.25",
            "roll_cost": "2.00",
            "average_win": "1.62",
        }

        sentence = _summary_sentence(summary)

        self.assertIn("roll +$2.00", sentence)

    def test_quant_panel_text_includes_roll_flow(self) -> None:
        from anki_slot_machine.ui.stats_dialog import _quant_panel_text

        text = _quant_panel_text(
            {
                "recent_10": {
                    "net": "3.25",
                    "roll_cost": "2.00",
                    "hit_count": 2,
                    "spin_count": 4,
                    "trend_arrow": "↑",
                    "trend_label": "accelerating",
                },
                "recent_50": {
                    "net": "7.00",
                    "roll_cost": "5.00",
                    "hit_count": 6,
                    "spin_count": 10,
                    "trend_arrow": "→",
                    "trend_label": "steady",
                },
                "recent_100": {
                    "net": "9.50",
                    "roll_cost": "8.00",
                    "hit_count": 12,
                    "spin_count": 18,
                    "trend_arrow": "↓",
                    "trend_label": "cooling off",
                },
                "current_streak": 2,
                "streak_context": "warming up",
                "best_streak": 4,
                "spin_win_rate": 55.0,
                "pair_hits": 5,
                "triple_hits": 1,
                "volatility_label": "balanced",
                "average_win": "1.25",
                "average_loss": "0.80",
                "best_win": "5.00",
                "worst_loss": "2.00",
                "biggest_jackpot": "5.00",
                "answer_counts": {"again": 1, "hard": 2, "good": 3, "easy": 4},
                "history_count": 10,
                "lifetime_roll_cost": "12.00",
                "lifetime_net": "4.75",
            }
        )

        self.assertIn("roll    +$2.00", text)
        self.assertIn("Roll flow", text)


if __name__ == "__main__":
    unittest.main()
