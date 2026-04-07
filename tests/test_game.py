from __future__ import annotations

import copy
import json
import random
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from test_support import install_stubs

install_stubs()

import anki_slot_machine.config as config_module
import anki_slot_machine.game as game_module


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
        return config_module.config_from_raw(raw)


class AnswerKeyTests(unittest.TestCase):
    def test_four_button_mapping(self) -> None:
        self.assertEqual(game_module.answer_key_for_rating(1, 4), "again")
        self.assertEqual(game_module.answer_key_for_rating(2, 4), "hard")
        self.assertEqual(game_module.answer_key_for_rating(3, 4), "good")
        self.assertEqual(game_module.answer_key_for_rating(4, 4), "easy")

    def test_three_button_mapping(self) -> None:
        self.assertEqual(game_module.answer_key_for_rating(1, 3), "again")
        self.assertEqual(game_module.answer_key_for_rating(2, 3), "good")
        self.assertEqual(game_module.answer_key_for_rating(3, 3), "easy")

    def test_two_button_mapping(self) -> None:
        self.assertEqual(game_module.answer_key_for_rating(1, 2), "again")
        self.assertEqual(game_module.answer_key_for_rating(2, 2), "good")


class ReelTests(unittest.TestCase):
    def test_weighted_symbol_uses_slot_faces(self) -> None:
        config = make_config(
            profile_overrides={
                "faces": {
                    "SLOT_1": 0,
                    "SLOT_2": 0,
                    "SLOT_3": 100,
                    "SLOT_4": 0,
                    "SLOT_5": 0,
                }
            }
        )
        self.assertEqual(
            game_module.weighted_symbol(config, rng=random.Random(1)),
            "SLOT_3",
        )

    def test_build_reel_strip_uses_slot_faces(self) -> None:
        config = make_config(
            profile_overrides={
                "faces": {
                    "SLOT_1": 2,
                    "SLOT_2": 1,
                    "SLOT_3": 0,
                    "SLOT_4": 0,
                    "SLOT_5": 0,
                }
            }
        )
        self.assertEqual(
            game_module.build_reel_strip(config),
            ("SLOT_1", "SLOT_1", "SLOT_2"),
        )

    def test_shuffled_reel_strip_preserves_population(self) -> None:
        config = make_config(
            profile_overrides={
                "faces": {
                    "SLOT_1": 2,
                    "SLOT_2": 1,
                    "SLOT_3": 0,
                    "SLOT_4": 0,
                    "SLOT_5": 0,
                }
            }
        )
        strip = game_module.shuffled_reel_strip(config, rng=random.Random(1))
        self.assertCountEqual(strip, ("SLOT_1", "SLOT_1", "SLOT_2"))

    def test_spin_reel_returns_symbol_from_strip(self) -> None:
        self.assertEqual(
            game_module.spin_reel(("SLOT_3",), rng=random.Random(1)),
            "SLOT_3",
        )

    def test_spin_reels_roll_three_independent_values(self) -> None:
        config = make_config(
            profile_overrides={
                "faces": {
                    "SLOT_1": 0,
                    "SLOT_2": 0,
                    "SLOT_3": 100,
                    "SLOT_4": 0,
                    "SLOT_5": 0,
                }
            }
        )
        self.assertEqual(
            game_module.spin_reels(config, rng=random.Random(1)),
            ("SLOT_3", "SLOT_3", "SLOT_3"),
        )


class RewardTests(unittest.TestCase):
    def test_matched_symbol_requires_three_of_a_kind(self) -> None:
        self.assertEqual(
            game_module.matched_symbol_for_reels(("SLOT_3", "SLOT_3", "SLOT_3")),
            "SLOT_3",
        )
        self.assertIsNone(
            game_module.matched_symbol_for_reels(("SLOT_1", "SLOT_3", "SLOT_2"))
        )

    def test_pair_symbol_requires_exact_pair(self) -> None:
        self.assertEqual(
            game_module.pair_symbol_for_reels(("SLOT_1", "SLOT_3", "SLOT_1")),
            "SLOT_1",
        )
        self.assertIsNone(
            game_module.pair_symbol_for_reels(("SLOT_3", "SLOT_3", "SLOT_3"))
        )
        self.assertIsNone(
            game_module.pair_symbol_for_reels(("SLOT_1", "SLOT_2", "SLOT_3"))
        )

    def test_evaluate_reels_reports_triples_pairs_and_misses(self) -> None:
        config = make_config()
        triple_multiplier = game_module.slot_triple_multiplier_for_symbol(
            config,
            "SLOT_4",
        )
        double_multiplier = game_module.slot_double_multiplier_for_symbol(
            config,
            "SLOT_2",
        )
        self.assertEqual(
            game_module.evaluate_reels(config, ("SLOT_4", "SLOT_4", "SLOT_4")),
            (triple_multiplier, "SLOT_4", 3),
        )
        self.assertEqual(
            game_module.evaluate_reels(config, ("SLOT_2", "SLOT_5", "SLOT_2")),
            (double_multiplier, "SLOT_2", 2),
        )
        self.assertEqual(
            game_module.evaluate_reels(config, ("SLOT_1", "SLOT_3", "SLOT_2")),
            (Decimal("0"), None, 1),
        )

    def test_slot_multiplier_for_reels_uses_evaluated_result(self) -> None:
        config = make_config()
        self.assertEqual(
            game_module.slot_multiplier_for_reels(
                config,
                ("SLOT_3", "SLOT_3", "SLOT_3"),
            ),
            config.slot_triple_multipliers["SLOT_3"],
        )
        self.assertEqual(
            game_module.slot_multiplier_for_reels(
                config,
                ("SLOT_2", "SLOT_2", "SLOT_4"),
            ),
            config.slot_double_multipliers["SLOT_2"],
        )
        self.assertEqual(
            game_module.slot_multiplier_for_reels(
                config,
                ("SLOT_1", "SLOT_3", "SLOT_2"),
            ),
            Decimal("0"),
        )

    def test_neutral_reels_use_first_three_symbols(self) -> None:
        config = make_config()
        self.assertEqual(game_module.neutral_reels(config), ("SLOT_1", "SLOT_2", "SLOT_3"))

    def test_spin_result_for_again_is_a_loss(self) -> None:
        config = make_config()
        result = game_module.build_spin_result(
            config,
            card_id=42,
            answer_key="again",
            bet=Decimal("1.00"),
            balance_before=Decimal("100.00"),
            rng=random.Random(2),
        )
        self.assertFalse(result.is_win)
        self.assertEqual(result.net_change, Decimal("-1.00"))
        self.assertEqual(result.balance_after, Decimal("99.00"))
        self.assertEqual(result.reels, ("MISS", "MISS", "MISS"))
        self.assertFalse(result.animation_enabled)
        self.assertFalse(result.did_spin)
        self.assertEqual(result.base_reward, Decimal("0"))
        self.assertEqual(result.slot_bonus, Decimal("0"))
        self.assertIsNone(result.matched_symbol)

    def test_spin_result_for_hard_is_neutral(self) -> None:
        config = make_config()
        result = game_module.build_spin_result(
            config,
            card_id=42,
            answer_key="hard",
            bet=Decimal("1.00"),
            balance_before=Decimal("100.00"),
            rng=random.Random(2),
        )
        self.assertFalse(result.is_win)
        self.assertEqual(result.net_change, Decimal("0.00"))
        self.assertEqual(result.balance_after, Decimal("100.00"))
        self.assertFalse(result.did_spin)
        self.assertEqual(result.base_reward, Decimal("0.00"))
        self.assertEqual(result.slot_bonus, Decimal("0.00"))
        self.assertIsNone(result.matched_symbol)

    def test_spin_result_for_good_uses_triple_multiplier(self) -> None:
        config = make_config()
        with patch.object(
            game_module,
            "spin_reels",
            return_value=("SLOT_3", "SLOT_3", "SLOT_3"),
        ):
            result = game_module.build_spin_result(
                config,
                card_id=42,
                answer_key="good",
                bet=Decimal("1.00"),
                balance_before=Decimal("100.00"),
                rng=random.Random(2),
            )
        self.assertTrue(result.is_win)
        self.assertTrue(result.did_spin)
        self.assertEqual(
            result.slot_multiplier,
            config.slot_triple_multipliers["SLOT_3"],
        )
        self.assertEqual(result.base_reward, Decimal("1.00"))
        self.assertEqual(result.slot_bonus, result.payout - Decimal("1.00"))
        self.assertEqual(result.matched_symbol, "SLOT_3")
        self.assertEqual(result.net_change, result.payout)
        self.assertEqual(result.balance_after, Decimal("100.00") + result.payout)

    def test_spin_result_for_good_uses_double_multiplier(self) -> None:
        config = make_config()
        with patch.object(
            game_module,
            "spin_reels",
            return_value=("SLOT_2", "SLOT_5", "SLOT_2"),
        ):
            result = game_module.build_spin_result(
                config,
                card_id=42,
                answer_key="good",
                bet=Decimal("1.00"),
                balance_before=Decimal("100.00"),
                rng=random.Random(2),
            )
        self.assertFalse(result.line_hit)
        self.assertEqual(result.matched_symbol, "SLOT_2")
        self.assertEqual(
            result.slot_multiplier,
            config.slot_double_multipliers["SLOT_2"],
        )
        self.assertEqual(result.payout, config.slot_double_multipliers["SLOT_2"])

    def test_spin_result_for_good_defaults_to_x0_when_reels_do_not_match(self) -> None:
        config = make_config()
        with patch.object(
            game_module,
            "spin_reels",
            return_value=("SLOT_1", "SLOT_3", "SLOT_2"),
        ):
            result = game_module.build_spin_result(
                config,
                card_id=42,
                answer_key="good",
                bet=Decimal("1.00"),
                balance_before=Decimal("100.00"),
                rng=random.Random(1),
            )
        self.assertFalse(result.line_hit)
        self.assertIsNone(result.matched_symbol)
        self.assertEqual(result.slot_multiplier, Decimal("0"))
        self.assertEqual(result.payout, Decimal("0.00"))
        self.assertFalse(result.is_win)

    def test_spin_result_for_easy_uses_double_base_times_multiplier(self) -> None:
        config = make_config()
        with patch.object(
            game_module,
            "spin_reels",
            return_value=("SLOT_4", "SLOT_4", "SLOT_4"),
        ):
            result = game_module.build_spin_result(
                config,
                card_id=42,
                answer_key="easy",
                bet=Decimal("1.00"),
                balance_before=Decimal("100.00"),
                rng=random.Random(2),
            )
        self.assertTrue(result.is_win)
        self.assertTrue(result.did_spin)
        self.assertEqual(
            result.slot_multiplier,
            config.slot_triple_multipliers["SLOT_4"],
        )
        self.assertEqual(result.base_reward, Decimal("2.00"))
        self.assertEqual(
            result.payout,
            (Decimal("2.00") * config.slot_triple_multipliers["SLOT_4"]).quantize(
                Decimal("0.01")
            ),
        )
        self.assertEqual(result.balance_after, Decimal("100.00") + result.payout)
        self.assertTrue(result.animation_enabled)


if __name__ == "__main__":
    unittest.main()
