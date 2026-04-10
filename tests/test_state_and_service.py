from __future__ import annotations

import copy
import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from test_support import install_stubs

install_stubs()

import anki_slot_machine.config as config_module
import anki_slot_machine.game as game_module
from anki_slot_machine.config import load_config
from anki_slot_machine.service import SlotMachineService
from anki_slot_machine.state import (
    BACKUP_SAVE_INTERVAL,
    UNDO_HISTORY_LIMIT,
    SlotMachineState,
    StateRepository,
)


def build_profile(**overrides) -> dict:
    profile = copy.deepcopy(config_module.DEFAULT_SLOT_PROFILE)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(profile.get(key), dict):
            profile[key] = {**profile[key], **value}
        else:
            profile[key] = value
    return profile


def make_config(*, profile_overrides=None, **config_overrides):
    raw = {
        "starting_balance": 100,
        "decimal_places": 2,
    }
    raw.update(config_overrides)
    profile = build_profile(**(profile_overrides or {}))
    with tempfile.TemporaryDirectory() as tmp_dir:
        profile_path = Path(tmp_dir) / "profile.json"
        profile_path.write_text(json.dumps(profile), encoding="utf-8")
        raw["slot_profile_path"] = str(profile_path)
        return load_config.__globals__["config_from_raw"](raw)


def make_multi_machine_config(*, profile_overrides=None, **config_overrides):
    raw = {
        "starting_balance": 100,
        "decimal_places": 2,
    }
    raw.update(config_overrides)
    profile = build_profile(**(profile_overrides or {}))
    with tempfile.TemporaryDirectory() as tmp_dir:
        profile_path = Path(tmp_dir) / "profile.json"
        profile_path.write_text(json.dumps(profile), encoding="utf-8")
        raw["slot_profile_path"] = str(profile_path)
        raw["machines"] = [
            {"key": "alpha", "label": "Alpha"},
            {"key": "beta", "label": "Beta"},
        ]
        return load_config.__globals__["config_from_raw"](raw)


def reel_positions_for_symbols(machine, symbols):
    strip = game_module.build_reel_strip(machine)
    return tuple(strip.index(symbol) for symbol in symbols)


class StateRepositoryTests(unittest.TestCase):
    def test_repository_writes_only_local_state_file_with_decimal_strings(self) -> None:
        config = make_config()
        state = SlotMachineState.initial(config)

        with tempfile.TemporaryDirectory() as tmp_dir:
            target = Path(tmp_dir) / "slot_machine_state.json"
            backup = Path(tmp_dir) / "slot_machine_state.json.bak"
            repository = StateRepository()
            with patch("anki_slot_machine.state.state_path", return_value=target):
                repository.save(state, config)
                self.assertTrue(target.exists())
                self.assertTrue(backup.exists())
                payload = json.loads(target.read_text(encoding="utf-8"))
                backup_payload = json.loads(backup.read_text(encoding="utf-8"))

        self.assertEqual(payload["balance"], "100.00")
        self.assertEqual(backup_payload["balance"], "100.00")
        self.assertNotIn("notes", payload)
        self.assertNotIn("cards", payload)

    def test_repository_defers_backup_refresh_between_intervals(self) -> None:
        config = make_config()
        repository = StateRepository()

        with tempfile.TemporaryDirectory() as tmp_dir:
            target = Path(tmp_dir) / "slot_machine_state.json"
            backup = Path(tmp_dir) / "slot_machine_state.json.bak"
            with patch("anki_slot_machine.state.state_path", return_value=target):
                first_state = SlotMachineState.initial(config)
                repository.save(first_state, config)
                first_backup_payload = backup.read_text(encoding="utf-8")

                second_state = SlotMachineState.initial(config)
                second_state.balance = Decimal("101.00")
                repository.save(second_state, config)

                self.assertEqual(
                    json.loads(target.read_text(encoding="utf-8"))["balance"],
                    "101.00",
                )
                self.assertEqual(
                    backup.read_text(encoding="utf-8"),
                    first_backup_payload,
                )

                for offset in range(BACKUP_SAVE_INTERVAL - 1):
                    next_state = SlotMachineState.initial(config)
                    next_state.balance = Decimal(f"{102 + offset}.00")
                    repository.save(next_state, config)

                self.assertEqual(
                    json.loads(backup.read_text(encoding="utf-8"))["balance"],
                    f"{101 + (BACKUP_SAVE_INTERVAL - 1):.2f}",
                )

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

    def test_repository_loads_backup_when_main_state_file_is_corrupted(self) -> None:
        config = make_config()
        valid_payload = {
            "balance": "111.25",
            "total_won": "12.50",
            "total_lost": "1.00",
            "history": [
                {
                    "event_id": "evt-1",
                    "timestamp": "2026-04-09T16:10:00+09:00",
                    "card_id": 9,
                    "answer_key": "good",
                    "answer_label": "Good",
                    "bet": "1.00",
                    "payout": "2.20",
                    "base_reward": "1.00",
                    "slot_bonus": "1.20",
                    "net_change": "2.20",
                    "balance_after": "111.25",
                    "reels": ["SLOT_4", "SLOT_4", "SLOT_2"],
                    "is_win": True,
                    "did_spin": True,
                    "line_hit": False,
                    "slot_multiplier": "2.20",
                    "matched_symbol": "SLOT_4",
                    "animation_enabled": True,
                    "headline": "Good lands a pair",
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            target = Path(tmp_dir) / "slot_machine_state.json"
            backup = Path(tmp_dir) / "slot_machine_state.json.bak"
            target.write_text("{broken json", encoding="utf-8")
            backup.write_text(json.dumps(valid_payload), encoding="utf-8")
            repository = StateRepository()
            with patch("anki_slot_machine.state.state_path", return_value=target):
                state = repository.load(config)

        self.assertEqual(state.balance, Decimal("111.25"))
        self.assertEqual(state.total_won, Decimal("12.50"))
        self.assertEqual(state.history[0]["card_id"], 9)

    def test_repository_drops_legacy_full_snapshot_undo_entries_on_load(self) -> None:
        config = make_config()
        legacy_undo_entry = {
            "balance": "99.00",
            "total_won": "5.00",
            "total_lost": "1.00",
            "spins": 3,
            "current_streak": 1,
            "best_streak": 2,
            "biggest_jackpot": "5.00",
            "daily_earnings": {"2026-04-07": "4.00"},
            "history": [
                {
                    "event_id": "legacy-evt-1",
                    "timestamp": "2026-04-07T10:00:00+09:00",
                    "card_id": 1,
                    "answer_key": "good",
                    "answer_label": "Good",
                    "bet": "1.00",
                    "payout": "2.00",
                    "base_reward": "1.00",
                    "slot_bonus": "1.00",
                    "net_change": "1.00",
                    "balance_after": "99.00",
                }
            ],
            "last_result": {
                "event_id": "legacy-evt-1",
                "timestamp": "2026-04-07T10:00:00+09:00",
                "card_id": 1,
                "answer_key": "good",
                "answer_label": "Good",
                "bet": "1.00",
                "payout": "2.00",
                "base_reward": "1.00",
                "slot_bonus": "1.00",
                "net_change": "1.00",
                "balance_after": "99.00",
            },
            "eligible_reviews_since_spin_check": 0,
        }
        payload = {
            "balance": "100.00",
            "undo_history": [legacy_undo_entry],
            "review_undo_stack": [True],
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            target = Path(tmp_dir) / "slot_machine_state.json"
            target.write_text(json.dumps(payload), encoding="utf-8")
            repository = StateRepository()
            with patch("anki_slot_machine.state.state_path", return_value=target):
                state = repository.load(config)

        self.assertEqual(state.undo_history, [])
        self.assertEqual(state.review_undo_stack, [])

    def test_restore_review_snapshot_restores_undo_internals(self) -> None:
        config = make_config()
        state = SlotMachineState.initial(config)
        payload = {
            "balance": "101.00",
            "undo_history": [
                {
                    "undo_format_version": 1,
                    "balance": "100.00",
                    "total_won": "0.00",
                    "total_lost": "0.00",
                    "spins": 0,
                    "current_streak": 0,
                    "best_streak": 0,
                    "biggest_jackpot": "0.00",
                    "daily_earnings_date": "",
                    "had_daily_earnings_entry": False,
                    "daily_earnings_previous_value": None,
                    "last_result": None,
                    "reel_positions": {},
                    "eligible_reviews_since_spin_check": 0,
                    "dropped_history_event": None,
                }
            ],
            "review_undo_stack": [True],
        }

        state.restore_review_snapshot(payload, config)

        self.assertEqual(len(state.undo_history), 1)
        self.assertEqual(state.review_undo_stack, [True])


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
        self.assertNotIn("fixed_bet_amount", snapshot)
        self.assertNotIn("default_slot_multiplier", snapshot)
        self.assertIn("reel_strip", snapshot["machines"][0])
        self.assertIn("reel_positions", snapshot["machines"][0])
        self.assertEqual(len(snapshot["machines"][0]["reel_positions"]), 3)
        self.assertEqual(snapshot["spin_animation_duration_ms"], 750)

    def test_default_spin_trigger_spins_every_eligible_review(self) -> None:
        config = make_config()
        with tempfile.TemporaryDirectory() as tmp_dir:
            service = self.make_service(config, Path(tmp_dir) / "state.json")
            service._rng = SimpleNamespace(random=lambda: 0.99)
            with patch(
                "anki_slot_machine.game.spin_reel_positions",
                return_value=reel_positions_for_symbols(config.machines[0], ("SLOT_3", "SLOT_3", "SLOT_3")),
            ):
                result = service.apply_review(card_id=1, ease=3, button_count=4)

        self.assertTrue(result.did_spin)
        self.assertEqual(service.state().eligible_reviews_since_spin_check, 0)

    def test_spin_trigger_every_n_waits_for_threshold(self) -> None:
        config = make_config(spin_trigger_every_n=3)
        with tempfile.TemporaryDirectory() as tmp_dir:
            service = self.make_service(config, Path(tmp_dir) / "state.json")
            service._rng = SimpleNamespace(random=lambda: 0.0)
            first = service.apply_review(card_id=1, ease=3, button_count=4)
            second = service.apply_review(card_id=2, ease=3, button_count=4)
            with patch(
                "anki_slot_machine.game.spin_reel_positions",
                return_value=reel_positions_for_symbols(config.machines[0], ("SLOT_3", "SLOT_3", "SLOT_3")),
            ):
                third = service.apply_review(card_id=3, ease=3, button_count=4)

        self.assertFalse(first.did_spin)
        self.assertEqual(first.payout, Decimal("0.00"))
        self.assertFalse(second.did_spin)
        self.assertEqual(second.payout, Decimal("0.00"))
        self.assertTrue(third.did_spin)
        self.assertEqual(service.state().eligible_reviews_since_spin_check, 0)

    def test_spin_trigger_chance_rolls_on_threshold_and_resets_counter(self) -> None:
        config = make_config(spin_trigger_every_n=2, spin_trigger_chance=Decimal("0.5"))
        with tempfile.TemporaryDirectory() as tmp_dir:
            service = self.make_service(config, Path(tmp_dir) / "state.json")
            service._rng = SimpleNamespace(random=lambda: 0.75)
            first = service.apply_review(card_id=1, ease=3, button_count=4)
            second = service.apply_review(card_id=2, ease=3, button_count=4)
            third = service.apply_review(card_id=3, ease=3, button_count=4)

        self.assertFalse(first.did_spin)
        self.assertFalse(second.did_spin)
        self.assertEqual(second.payout, Decimal("0.00"))
        self.assertFalse(third.did_spin)
        self.assertEqual(service.state().eligible_reviews_since_spin_check, 1)

    def test_loss_updates_balance_and_stats_without_touching_card_data(self) -> None:
        config = make_config(answer_base_values={"again": -1})
        with tempfile.TemporaryDirectory() as tmp_dir:
            service = self.make_service(config, Path(tmp_dir) / "state.json")
            with patch(
                "anki_slot_machine.game.spin_reel_positions",
                return_value=reel_positions_for_symbols(config.machines[0], ("SLOT_2", "SLOT_5", "SLOT_2")),
            ):
                result = service.apply_review(card_id=55, ease=1, button_count=4)
            snapshot = service.stats_snapshot()

        self.assertEqual(result.card_id, 55)
        self.assertEqual(result.answer_key, "again")
        self.assertEqual(snapshot["balance"], result.to_dict(2)["balance_after"])
        self.assertEqual(snapshot["total_lost"], "0.95")
        self.assertEqual(snapshot["spins"], 1)

    def test_hard_is_neutral_and_does_not_spin_when_configured_to_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            service = self.make_service(
                make_config(answer_base_values={"hard": 0}),
                Path(tmp_dir) / "state.json",
            )
            result = service.apply_review(card_id=99, ease=2, button_count=4)
            snapshot = service.stats_snapshot()

        self.assertEqual(result.answer_key, "hard")
        self.assertTrue(result.no_spin)
        self.assertEqual(snapshot["balance"], "100.00")
        self.assertEqual(snapshot["total_won"], "0.00")
        self.assertEqual(snapshot["spins"], 0)
        self.assertEqual(snapshot["best_streak"], 0)
        self.assertEqual(service.state().eligible_reviews_since_spin_check, 0)

    def test_hard_no_op_does_not_create_slot_undo_or_history_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            service = self.make_service(
                make_config(answer_base_values={"hard": 0}),
                Path(tmp_dir) / "state.json",
            )
            service.apply_review(card_id=99, ease=2, button_count=4)

            self.assertFalse(service.snapshot()["can_undo"])
            self.assertEqual(service.state().history, [])
            self.assertEqual(service.state().undo_history, [])
            self.assertEqual(service.state().daily_earnings, {})
            self.assertEqual(service.state().review_undo_stack, [False])
            self.assertFalse(service.undo_last_review())

        self.assertEqual(service.state().review_undo_stack, [])

    def test_hard_uses_default_positive_value_with_spinning(self) -> None:
        config = make_config()
        with tempfile.TemporaryDirectory() as tmp_dir:
            service = self.make_service(config, Path(tmp_dir) / "state.json")
            with patch(
                "anki_slot_machine.game.spin_reel_positions",
                return_value=reel_positions_for_symbols(
                    config.machines[0], ("SLOT_2", "SLOT_5", "SLOT_2")
                ),
            ):
                result = service.apply_review(card_id=99, ease=2, button_count=4)
            snapshot = service.stats_snapshot()

        self.assertEqual(result.answer_key, "hard")
        self.assertTrue(result.did_spin)
        self.assertEqual(result.payout, Decimal("0.48"))
        self.assertEqual(snapshot["balance"], "100.48")
        self.assertEqual(snapshot["total_won"], "0.48")
        self.assertEqual(snapshot["spins"], 1)

    def test_hard_uses_configured_signed_value_with_spinning(self) -> None:
        config = make_config(answer_base_values={"hard": -0.5})
        with tempfile.TemporaryDirectory() as tmp_dir:
            service = self.make_service(config, Path(tmp_dir) / "state.json")
            with patch(
                "anki_slot_machine.game.spin_reel_positions",
                return_value=reel_positions_for_symbols(
                    config.machines[0], ("SLOT_2", "SLOT_5", "SLOT_2")
                ),
            ):
                result = service.apply_review(card_id=99, ease=2, button_count=4)
            snapshot = service.stats_snapshot()

        self.assertEqual(result.answer_key, "hard")
        self.assertTrue(result.did_spin)
        self.assertEqual(result.payout, Decimal("-0.48"))
        self.assertEqual(snapshot["balance"], "99.52")
        self.assertEqual(snapshot["total_lost"], "0.48")
        self.assertEqual(snapshot["spins"], 1)

    def test_zero_good_value_does_not_spin_or_advance_trigger_counter(self) -> None:
        config = make_config(answer_base_values={"good": 0}, spin_trigger_every_n=2)
        with tempfile.TemporaryDirectory() as tmp_dir:
            service = self.make_service(config, Path(tmp_dir) / "state.json")
            first = service.apply_review(card_id=99, ease=3, button_count=4)
            second = service.apply_review(card_id=100, ease=3, button_count=4)

        self.assertFalse(first.did_spin)
        self.assertFalse(second.did_spin)
        self.assertTrue(first.no_spin)
        self.assertTrue(second.no_spin)
        self.assertEqual(first.payout, Decimal("0.00"))
        self.assertEqual(second.payout, Decimal("0.00"))
        self.assertEqual(service.state().eligible_reviews_since_spin_check, 0)

    def test_zero_again_value_does_not_spin(self) -> None:
        config = make_config(answer_base_values={"again": 0})
        with tempfile.TemporaryDirectory() as tmp_dir:
            service = self.make_service(config, Path(tmp_dir) / "state.json")
            result = service.apply_review(card_id=55, ease=1, button_count=4)
            review_snapshot = service.snapshot()
            snapshot = service.stats_snapshot()

        self.assertFalse(result.did_spin)
        self.assertTrue(result.no_spin)
        self.assertEqual(result.payout, Decimal("0.00"))
        self.assertIsNotNone(review_snapshot["last_result"])
        self.assertEqual(review_snapshot["last_result"]["answer_key"], "again")
        self.assertTrue(review_snapshot["last_result"]["no_spin"])
        self.assertEqual(snapshot["spins"], 0)
        self.assertEqual(snapshot["balance"], "100.00")

    def test_good_updates_balance_streak_and_history_with_decimal_payout(self) -> None:
        config = make_config(answer_base_values={"hard": 0})
        with tempfile.TemporaryDirectory() as tmp_dir:
            service = self.make_service(config, Path(tmp_dir) / "state.json")
            with patch(
                "anki_slot_machine.game.spin_reel_positions",
                return_value=reel_positions_for_symbols(config.machines[0], ("SLOT_3", "SLOT_3", "SLOT_3")),
            ):
                result = service.apply_review(card_id=99, ease=3, button_count=4)
            snapshot = service.stats_snapshot()

        expected_payout = result.to_dict(config.decimal_places)["payout"]
        self.assertEqual(result.answer_key, "good")
        self.assertEqual(snapshot["total_won"], expected_payout)
        self.assertEqual(snapshot["spins"], 1)
        self.assertEqual(snapshot["best_streak"], 1)
        self.assertEqual(snapshot["history"][0]["card_id"], 99)
        self.assertEqual(snapshot["history"][0]["history_format_version"], 2)
        self.assertIn("slot_instance_key", snapshot["history"][0])
        self.assertIn("slot_instance_label", snapshot["history"][0])
        self.assertIn("reel_positions", snapshot["history"][0])

    def test_snapshot_tracks_current_reel_positions_for_machine(self) -> None:
        config = make_config()
        strip = game_module.build_reel_strip(config.machines[0])
        reel_positions = (
            strip.index("SLOT_3"),
            strip.index("SLOT_3"),
            strip.index("SLOT_3"),
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            service = self.make_service(config, Path(tmp_dir) / "state.json")
            with patch(
                "anki_slot_machine.game.spin_reel_positions",
                return_value=reel_positions,
            ):
                result = service.apply_review(card_id=99, ease=3, button_count=4)
            snapshot = service.snapshot()

        self.assertEqual(
            snapshot["machines"][0]["reel_positions"],
            list(result.reel_positions),
        )

    def test_stats_snapshot_exposes_graph_history_in_oldest_to_newest_order(self) -> None:
        config = make_config()
        with tempfile.TemporaryDirectory() as tmp_dir:
            service = self.make_service(config, Path(tmp_dir) / "state.json")
            with patch(
                "anki_slot_machine.game.spin_reel_positions",
                return_value=reel_positions_for_symbols(config.machines[0], ("SLOT_2", "SLOT_2", "SLOT_3")),
            ):
                first = service.apply_review(card_id=1, ease=3, button_count=4)
            with patch(
                "anki_slot_machine.game.spin_reel_positions",
                return_value=reel_positions_for_symbols(config.machines[0], ("SLOT_5", "SLOT_5", "SLOT_5")),
            ):
                second = service.apply_review(card_id=2, ease=3, button_count=4)
            snapshot = service.stats_snapshot()

        self.assertEqual(snapshot["graph_history"][0]["card_id"], first.card_id)
        self.assertEqual(snapshot["graph_history"][-1]["card_id"], second.card_id)

    def test_stats_snapshot_exposes_extended_roll_metrics(self) -> None:
        config = make_config()
        with tempfile.TemporaryDirectory() as tmp_dir:
            service = self.make_service(config, Path(tmp_dir) / "state.json")
            with patch(
                "anki_slot_machine.game.spin_reel_positions",
                return_value=reel_positions_for_symbols(config.machines[0], ("SLOT_2", "SLOT_2", "SLOT_3")),
            ):
                service.apply_review(card_id=1, ease=3, button_count=4)
            with patch(
                "anki_slot_machine.game.spin_reel_positions",
                return_value=reel_positions_for_symbols(config.machines[0], ("SLOT_5", "SLOT_5", "SLOT_5")),
            ):
                service.apply_review(card_id=2, ease=4, button_count=4)
            with patch(
                "anki_slot_machine.game.spin_reel_positions",
                return_value=reel_positions_for_symbols(
                    config.machines[0], ("SLOT_1", "SLOT_3", "SLOT_4")
                ),
            ):
                service.apply_review(card_id=3, ease=2, button_count=4)
            snapshot = service.stats_snapshot()

        self.assertIn("lifetime_net", snapshot)
        self.assertIn("spin_win_rate", snapshot)
        self.assertIn("pair_hits", snapshot)
        self.assertIn("triple_hits", snapshot)
        self.assertIn("answer_counts", snapshot)
        self.assertIn("best_win", snapshot)
        self.assertIn("worst_loss", snapshot)
        self.assertIn("recent_100_net", snapshot)
        self.assertIn("recent_100_spin_win_rate", snapshot)
        self.assertIn("recent_high_balance", snapshot)
        self.assertIn("recent_low_balance", snapshot)
        self.assertIn("today_net", snapshot)
        self.assertIn("streak_context", snapshot)
        self.assertIn("session_temperature", snapshot)
        self.assertIn("volatility_label", snapshot)
        self.assertIn("recent_10", snapshot)
        self.assertIn("recent_50", snapshot)
        self.assertIn("recent_100", snapshot)
        self.assertEqual(snapshot["pair_hits"], 1)
        self.assertEqual(snapshot["triple_hits"], 1)
        self.assertEqual(snapshot["answer_counts"]["good"], 1)
        self.assertEqual(snapshot["answer_counts"]["easy"], 1)
        self.assertEqual(snapshot["answer_counts"]["hard"], 1)
        self.assertEqual(snapshot["worst_loss"], "0.00")

    def test_stats_snapshot_recent_windows_include_context_and_counts(self) -> None:
        config = make_config()
        with tempfile.TemporaryDirectory() as tmp_dir:
            service = self.make_service(config, Path(tmp_dir) / "state.json")
            with patch(
                "anki_slot_machine.game.spin_reel_positions",
                side_effect=[
                    reel_positions_for_symbols(config.machines[0], ("SLOT_2", "SLOT_2", "SLOT_4")),
                    reel_positions_for_symbols(config.machines[0], ("SLOT_5", "SLOT_5", "SLOT_5")),
                    reel_positions_for_symbols(config.machines[0], ("SLOT_1", "SLOT_3", "SLOT_4")),
                ],
            ):
                service.apply_review(card_id=1, ease=3, button_count=4)
                service.apply_review(card_id=2, ease=4, button_count=4)
                service.apply_review(card_id=3, ease=3, button_count=4)
            snapshot = service.stats_snapshot()

        self.assertEqual(snapshot["streak_context"], "cooled off")
        self.assertEqual(snapshot["recent_10"]["review_count"], 3)
        self.assertEqual(snapshot["recent_10"]["spin_count"], 3)
        self.assertEqual(snapshot["recent_10"]["hit_count"], 2)
        self.assertEqual(snapshot["recent_10"]["trend_direction"], "up")
        self.assertEqual(snapshot["recent_100"]["review_count"], 3)
        self.assertEqual(snapshot["recent_50"]["review_count"], 3)
        self.assertEqual(snapshot["today_net"], snapshot["lifetime_net"])
        self.assertTrue(snapshot["session_temperature"])
        self.assertTrue(snapshot["volatility_label"])

    def test_stats_snapshot_tracks_best_and_recent_balance_metrics(self) -> None:
        config = make_config()
        with tempfile.TemporaryDirectory() as tmp_dir:
            service = self.make_service(config, Path(tmp_dir) / "state.json")
            with patch(
                "anki_slot_machine.game.spin_reel_positions",
                return_value=reel_positions_for_symbols(config.machines[0], ("SLOT_5", "SLOT_5", "SLOT_5")),
            ):
                service.apply_review(card_id=1, ease=4, button_count=4)
            with patch(
                "anki_slot_machine.game.spin_reel_positions",
                return_value=reel_positions_for_symbols(config.machines[0], ("SLOT_2", "SLOT_3", "SLOT_4")),
            ):
                service.apply_review(card_id=2, ease=3, button_count=4)
            service.apply_review(card_id=3, ease=1, button_count=4)
            snapshot = service.stats_snapshot()

        self.assertNotEqual(snapshot["best_win"], "0.00")
        self.assertGreaterEqual(float(snapshot["worst_loss"]), 0.0)
        self.assertGreaterEqual(
            float(snapshot["recent_high_balance"]),
            float(snapshot["recent_low_balance"]),
        )
        self.assertGreaterEqual(
            float(snapshot["recent_high_balance"]),
            float(snapshot["balance"]),
        )
        self.assertLessEqual(
            float(snapshot["recent_low_balance"]),
            float(snapshot["balance"]),
        )
        self.assertNotEqual(snapshot["recent_100_net"], "0.00")

    def test_easy_pays_double_base_times_multiplier(self) -> None:
        config = make_config()
        with tempfile.TemporaryDirectory() as tmp_dir:
            service = self.make_service(config, Path(tmp_dir) / "state.json")
            with patch(
                "anki_slot_machine.game.spin_reel_positions",
                return_value=reel_positions_for_symbols(config.machines[0], ("SLOT_4", "SLOT_4", "SLOT_4")),
            ):
                result = service.apply_review(card_id=77, ease=4, button_count=4)
            snapshot = service.stats_snapshot()

        self.assertEqual(result.answer_key, "easy")
        self.assertEqual(
            snapshot["total_won"],
            result.to_dict(config.decimal_places)["payout"],
        )
        self.assertEqual(snapshot["spins"], 1)

    def test_negative_good_value_counts_as_loss(self) -> None:
        config = make_config(answer_base_values={"good": -1})
        with tempfile.TemporaryDirectory() as tmp_dir:
            service = self.make_service(config, Path(tmp_dir) / "state.json")
            with patch(
                "anki_slot_machine.game.spin_reel_positions",
                return_value=reel_positions_for_symbols(config.machines[0], ("SLOT_2", "SLOT_5", "SLOT_2")),
            ):
                result = service.apply_review(card_id=77, ease=3, button_count=4)
            snapshot = service.stats_snapshot()

        self.assertEqual(result.payout, Decimal("-0.95"))
        self.assertEqual(snapshot["total_lost"], "0.95")
        self.assertEqual(snapshot["total_won"], "0.00")

    def test_multi_machine_round_aggregates_into_shared_balance_and_history(self) -> None:
        config = make_multi_machine_config()
        with tempfile.TemporaryDirectory() as tmp_dir:
            service = self.make_service(config, Path(tmp_dir) / "state.json")
            with patch(
                "anki_slot_machine.game.spin_reel_positions",
                side_effect=[
                    reel_positions_for_symbols(config.machines[0], ("SLOT_1", "SLOT_1", "SLOT_1")),
                    reel_positions_for_symbols(config.machines[1], ("SLOT_2", "SLOT_5", "SLOT_2")),
                ],
            ):
                result = service.apply_review(card_id=88, ease=3, button_count=4)
            snapshot = service.stats_snapshot()

        self.assertEqual(len(result.machine_results), 2)
        self.assertEqual(result.payout, Decimal("3.45"))
        self.assertEqual(snapshot["balance"], "103.45")
        self.assertEqual(snapshot["spins"], 2)
        self.assertEqual(len(snapshot["history"][0]["machine_results"]), 2)
        self.assertEqual(snapshot["history"][0]["machine_results"][0]["machine_key"], "alpha")
        self.assertEqual(snapshot["history"][0]["machine_results"][1]["machine_key"], "beta")

    def test_multi_machine_again_cannot_overdraw_shared_bankroll(self) -> None:
        config = make_multi_machine_config(
            starting_balance=2,
            answer_base_values={"again": -1},
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            service = self.make_service(config, Path(tmp_dir) / "state.json")
            with patch(
                "anki_slot_machine.game.spin_reel_positions",
                side_effect=[
                    reel_positions_for_symbols(config.machines[0], ("SLOT_4", "SLOT_4", "SLOT_4")),
                    reel_positions_for_symbols(config.machines[1], ("SLOT_4", "SLOT_4", "SLOT_4")),
                ],
            ):
                result = service.apply_review(card_id=5, ease=1, button_count=4)
            snapshot = service.stats_snapshot()

        self.assertEqual(result.payout, Decimal("-2.00"))
        self.assertEqual(result.balance_after, Decimal("0.00"))
        self.assertEqual(result.machine_results[0]["payout"], "-2.00")
        self.assertEqual(result.machine_results[1]["payout"], "0.00")
        self.assertEqual(snapshot["balance"], "0.00")

    def test_undo_last_review_restores_previous_slot_state(self) -> None:
        config = make_config(spin_trigger_every_n=3)
        with tempfile.TemporaryDirectory() as tmp_dir:
            state_file = Path(tmp_dir) / "state.json"
            service = self.make_service(config, state_file)
            first = service.apply_review(card_id=11, ease=1, button_count=4)
            service.apply_review(card_id=12, ease=3, button_count=4)
            expected_snapshot = service.snapshot()
            expected_stats = service.stats_snapshot()
            with patch(
                "anki_slot_machine.game.spin_reel_positions",
                return_value=reel_positions_for_symbols(config.machines[0], ("SLOT_3", "SLOT_3", "SLOT_3")),
            ):
                service.apply_review(card_id=13, ease=3, button_count=4)

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
        self.assertEqual(reloaded.state().eligible_reviews_since_spin_check, 1)

    def test_undo_last_review_returns_false_without_review_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            service = self.make_service(make_config(), Path(tmp_dir) / "state.json")

            self.assertFalse(service.undo_last_review())

    def test_no_op_review_does_not_consume_previous_real_slot_undo(self) -> None:
        config = make_config(answer_base_values={"hard": 0})
        with tempfile.TemporaryDirectory() as tmp_dir:
            state_file = Path(tmp_dir) / "state.json"
            service = self.make_service(config, state_file)
            with patch(
                "anki_slot_machine.game.spin_reel_positions",
                return_value=reel_positions_for_symbols(
                    config.machines[0], ("SLOT_3", "SLOT_3", "SLOT_3")
                ),
            ):
                service.apply_review(card_id=1, ease=3, button_count=4)
            state_after_real_review = service.snapshot()

            service.apply_review(card_id=2, ease=2, button_count=4)
            after_no_op_snapshot = service.snapshot()
            self.assertFalse(after_no_op_snapshot["can_undo"])
            self.assertFalse(service.undo_last_review())
            self.assertEqual(after_no_op_snapshot["balance"], state_after_real_review["balance"])
            self.assertNotEqual(after_no_op_snapshot["last_result"], state_after_real_review["last_result"])
            self.assertEqual(after_no_op_snapshot["last_result"]["answer_key"], "hard")
            self.assertTrue(after_no_op_snapshot["last_result"]["no_spin"])

            self.assertTrue(service.undo_last_review())

        self.assertEqual(service.snapshot()["balance"], "100.00")

    def test_persisted_undo_history_uses_compact_records(self) -> None:
        config = make_config()
        with tempfile.TemporaryDirectory() as tmp_dir:
            state_file = Path(tmp_dir) / "state.json"
            service = self.make_service(config, state_file)
            service.apply_review(card_id=1, ease=3, button_count=4)
            service.apply_review(card_id=2, ease=3, button_count=4)
            service.apply_review(card_id=3, ease=3, button_count=4)

            payload = json.loads(state_file.read_text(encoding="utf-8"))

        undo_entry = payload["undo_history"][0]
        self.assertEqual(undo_entry["undo_format_version"], 1)
        self.assertNotIn("history", undo_entry)
        self.assertNotIn("undo_history", undo_entry)
        self.assertNotIn("daily_earnings", undo_entry)
        self.assertIn("daily_earnings_date", undo_entry)
        self.assertIn("dropped_history_event", undo_entry)

    def test_persisted_state_size_grows_roughly_linearly_across_reviews(self) -> None:
        config = make_config()
        with tempfile.TemporaryDirectory() as tmp_dir:
            state_file = Path(tmp_dir) / "state.json"
            service = self.make_service(config, state_file)
            for card_id in range(1, 11):
                service.apply_review(card_id=card_id, ease=2, button_count=4)
            size_after_ten = len(state_file.read_text(encoding="utf-8"))

            for card_id in range(11, 21):
                service.apply_review(card_id=card_id, ease=2, button_count=4)
            size_after_twenty = len(state_file.read_text(encoding="utf-8"))

        self.assertLess(size_after_twenty, size_after_ten * 2.5)

    def test_undo_retention_is_capped_separately_from_history(self) -> None:
        config = make_config()
        with tempfile.TemporaryDirectory() as tmp_dir:
            state_file = Path(tmp_dir) / "state.json"
            service = self.make_service(config, state_file)
            for card_id in range(1, UNDO_HISTORY_LIMIT + 8):
                service.apply_review(card_id=card_id, ease=3, button_count=4)

        self.assertEqual(len(service.state().undo_history), UNDO_HISTORY_LIMIT)
        self.assertEqual(len(service.state().review_undo_stack), UNDO_HISTORY_LIMIT)

    def test_again_uses_configured_signed_value_even_at_low_balance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            service = self.make_service(
                make_config(starting_balance=2, answer_base_values={"again": -1}),
                Path(tmp_dir) / "state.json",
            )
            config = service.config()
            with patch(
                "anki_slot_machine.game.spin_reel_positions",
                return_value=reel_positions_for_symbols(config.machines[0], ("SLOT_5", "SLOT_5", "SLOT_5")),
            ):
                result = service.apply_review(card_id=3, ease=1, button_count=4)
            snapshot = service.snapshot()

        self.assertEqual(result.base_reward, Decimal("-1.00"))
        self.assertEqual(result.balance_after, Decimal("0.00"))
        self.assertEqual(snapshot["balance"], "0.00")


if __name__ == "__main__":
    unittest.main()
