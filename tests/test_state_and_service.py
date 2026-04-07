from __future__ import annotations

import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from test_support import install_stubs

install_stubs()

from anki_slot_machine.config import load_config
from anki_slot_machine.service import SlotMachineService
from anki_slot_machine.state import SlotMachineState, StateRepository


def make_config(**overrides):
    raw = {
        "starting_balance": 100,
        "expected_multiplier_target": 1.10,
        "decimal_places": 2,
        "rarity_exponent": 1.6,
        "pair_scale_multiplier": 1,
        "triple_scale_multiplier": 6,
        "slot_faces": {
            "SLOT_1": 50,
            "SLOT_2": 28,
            "SLOT_3": 15,
            "SLOT_4": 6,
            "SLOT_5": 1,
        },
    }
    raw.update(overrides)
    return load_config.__globals__["config_from_raw"](raw)


class StateRepositoryTests(unittest.TestCase):
    def test_repository_writes_only_local_state_file_with_decimal_strings(self) -> None:
        config = make_config()
        state = SlotMachineState.initial(config)

        with tempfile.TemporaryDirectory() as tmp_dir:
            target = Path(tmp_dir) / "slot_machine_state.json"
            repository = StateRepository()
            with patch("anki_slot_machine.state.state_path", return_value=target):
                repository.save(state, config)
                self.assertTrue(target.exists())
                payload = json.loads(target.read_text(encoding="utf-8"))

        self.assertEqual(payload["balance"], "100.00")
        self.assertNotIn("notes", payload)
        self.assertNotIn("cards", payload)

    def test_repository_loads_old_integer_state_cleanly(self) -> None:
        config = make_config()
        legacy_payload = {
            "balance": 99,
            "total_won": 5,
            "total_lost": 1,
            "biggest_jackpot": 5,
            "daily_earnings": {"2026-04-07": 4},
            "last_result": {
                "event_id": "1",
                "timestamp": "2026-04-07T10:00:00+09:00",
                "card_id": 1,
                "answer_key": "good",
                "answer_label": "Good",
                "bet": 1,
                "payout": 2,
                "base_reward": 1,
                "slot_bonus": 1,
                "net_change": 2,
                "balance_after": 99,
                "reels": ["SLOT_1", "SLOT_1", "SLOT_1"],
                "is_win": True,
                "did_spin": True,
                "line_hit": True,
                "slot_multiplier": 2,
                "matched_symbol": "SLOT_1",
                "animation_enabled": True,
                "headline": "Good wins",
            },
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            target = Path(tmp_dir) / "slot_machine_state.json"
            target.write_text(json.dumps(legacy_payload), encoding="utf-8")
            repository = StateRepository()
            with patch("anki_slot_machine.state.state_path", return_value=target):
                state = repository.load(config)

        self.assertEqual(state.balance, Decimal("99.00"))
        self.assertEqual(state.total_won, Decimal("5.00"))
        self.assertEqual(state.daily_earnings["2026-04-07"], Decimal("4.00"))
        self.assertEqual(state.last_result["payout"], "2.00")


class ServiceTests(unittest.TestCase):
    def make_service(self, config, state_file: Path) -> SlotMachineService:
        service = SlotMachineService()
        self.addCleanup(patch.stopall)
        patch("anki_slot_machine.service.load_config", return_value=config).start()
        patch("anki_slot_machine.state.state_path", return_value=state_file).start()
        return service

    def test_snapshot_exposes_json_safe_decimal_strings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            service = self.make_service(make_config(), Path(tmp_dir) / "state.json")
            snapshot = service.snapshot()

        self.assertEqual(snapshot["balance"], "100.00")
        self.assertEqual(snapshot["fixed_bet_amount"], "1.00")
        self.assertEqual(snapshot["default_slot_multiplier"], "0.00")

    def test_set_bet_is_a_no_op_in_fixed_stake_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            service = self.make_service(make_config(), Path(tmp_dir) / "state.json")
            service.set_bet("10")
            service.apply_review(card_id=1, ease=1, button_count=4)
            snapshot = service.snapshot()

        self.assertEqual(snapshot["balance"], "99.00")
        self.assertEqual(snapshot["fixed_bet_amount"], "1.00")

    def test_loss_updates_balance_and_stats_without_touching_card_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            service = self.make_service(make_config(), Path(tmp_dir) / "state.json")
            result = service.apply_review(card_id=55, ease=1, button_count=4)
            snapshot = service.stats_snapshot()

        self.assertEqual(result.card_id, 55)
        self.assertEqual(result.answer_key, "again")
        self.assertEqual(snapshot["balance"], "99.00")
        self.assertEqual(snapshot["total_lost"], "1.00")
        self.assertEqual(snapshot["spins"], 0)

    def test_hard_is_neutral_and_does_not_spin(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            service = self.make_service(make_config(), Path(tmp_dir) / "state.json")
            result = service.apply_review(card_id=99, ease=2, button_count=4)
            snapshot = service.stats_snapshot()

        self.assertEqual(result.answer_key, "hard")
        self.assertEqual(snapshot["balance"], "100.00")
        self.assertEqual(snapshot["total_won"], "0.00")
        self.assertEqual(snapshot["spins"], 0)
        self.assertEqual(snapshot["best_streak"], 0)

    def test_good_updates_balance_streak_and_history_with_decimal_payout(self) -> None:
        config = make_config()
        with tempfile.TemporaryDirectory() as tmp_dir:
            service = self.make_service(config, Path(tmp_dir) / "state.json")
            with patch(
                "anki_slot_machine.game.spin_reels",
                return_value=("SLOT_3", "SLOT_3", "SLOT_3"),
            ):
                result = service.apply_review(card_id=99, ease=3, button_count=4)
            snapshot = service.stats_snapshot()

        expected_payout = result.to_dict(config.decimal_places)["payout"]
        self.assertEqual(result.answer_key, "good")
        self.assertEqual(snapshot["total_won"], expected_payout)
        self.assertEqual(snapshot["spins"], 1)
        self.assertEqual(snapshot["best_streak"], 1)
        self.assertEqual(snapshot["history"][0]["card_id"], 99)

    def test_easy_pays_double_base_times_multiplier(self) -> None:
        config = make_config()
        with tempfile.TemporaryDirectory() as tmp_dir:
            service = self.make_service(config, Path(tmp_dir) / "state.json")
            with patch(
                "anki_slot_machine.game.spin_reels",
                return_value=("SLOT_4", "SLOT_4", "SLOT_4"),
            ):
                result = service.apply_review(card_id=77, ease=4, button_count=4)
            snapshot = service.stats_snapshot()

        self.assertEqual(result.answer_key, "easy")
        self.assertEqual(snapshot["total_won"], result.to_dict(config.decimal_places)["payout"])
        self.assertEqual(snapshot["spins"], 1)

    def test_undo_last_review_restores_previous_slot_state(self) -> None:
        config = make_config()
        with tempfile.TemporaryDirectory() as tmp_dir:
            state_file = Path(tmp_dir) / "state.json"
            service = self.make_service(config, state_file)
            first = service.apply_review(card_id=11, ease=1, button_count=4)
            expected_snapshot = service.snapshot()
            expected_stats = service.stats_snapshot()
            with patch(
                "anki_slot_machine.game.spin_reels",
                return_value=("SLOT_3", "SLOT_3", "SLOT_3"),
            ):
                service.apply_review(card_id=12, ease=3, button_count=4)

            self.assertTrue(service.undo_last_review())

            restored_snapshot = service.snapshot()
            restored_stats = service.stats_snapshot()

            reloaded = self.make_service(config, state_file)
            reloaded_snapshot = reloaded.snapshot()
            reloaded_stats = reloaded.stats_snapshot()

        self.assertEqual(first.answer_key, "again")
        self.assertEqual(restored_snapshot, expected_snapshot)
        self.assertEqual(restored_stats, expected_stats)
        self.assertEqual(reloaded_snapshot, expected_snapshot)
        self.assertEqual(reloaded_stats, expected_stats)

    def test_undo_last_review_returns_false_without_review_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            service = self.make_service(make_config(), Path(tmp_dir) / "state.json")

            self.assertFalse(service.undo_last_review())

    def test_again_uses_fixed_one_dollar_stake_even_at_low_balance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            service = self.make_service(
                make_config(starting_balance=2),
                Path(tmp_dir) / "state.json",
            )
            result = service.apply_review(card_id=3, ease=1, button_count=4)
            snapshot = service.snapshot()

        self.assertEqual(result.net_change, Decimal("-1.00"))
        self.assertEqual(snapshot["balance"], "1.00")


if __name__ == "__main__":
    unittest.main()
