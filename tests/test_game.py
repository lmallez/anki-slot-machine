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
        strip = game_module.build_reel_strip(config)
        self.assertCountEqual(strip, ("SLOT_1", "SLOT_1", "SLOT_2"))
        self.assertEqual(game_module.build_reel_strip(config), strip)

    def test_build_reel_strip_spreads_symbols_when_possible(self) -> None:
        config = make_config(
            profile_overrides={
                "faces": {
                    "SLOT_1": 2,
                    "SLOT_2": 2,
                    "SLOT_3": 1,
                    "SLOT_4": 0,
                    "SLOT_5": 0,
                }
            }
        )
        strip = game_module.build_reel_strip(config)
        self.assertCountEqual(strip, ("SLOT_1", "SLOT_1", "SLOT_2", "SLOT_2", "SLOT_3"))
        self.assertTrue(
            all(strip[index] != strip[index + 1] for index in range(len(strip) - 1))
        )
        self.assertNotEqual(strip[0], strip[-1])

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

    def test_spin_reel_position_returns_index_from_strip(self) -> None:
        self.assertEqual(
            game_module.spin_reel_position(("SLOT_3",), rng=random.Random(1)),
            0,
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

    def test_spin_reel_positions_follow_reel_strip_population(self) -> None:
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
        positions = game_module.spin_reel_positions(config, rng=random.Random(1))
        self.assertEqual(
            game_module.visible_reels_for_positions(config, positions),
            ("SLOT_3", "SLOT_3", "SLOT_3"),
        )

    def test_advance_reel_to_symbol_uses_real_strip_and_minimum_steps(self) -> None:
        strip = ("SLOT_1", "SLOT_1", "SLOT_2", "SLOT_3")
        end_position, step_count = game_module.advance_reel_to_symbol(
            strip,
            start_position=0,
            target_symbol="SLOT_2",
            min_steps=6,
            rng=random.Random(1),
        )
        self.assertEqual(strip[end_position], "SLOT_2")
        self.assertGreaterEqual(step_count, 6)

    def test_advance_reel_to_position_preserves_backend_selected_stop(self) -> None:
        strip = ("SLOT_1", "SLOT_1", "SLOT_2", "SLOT_3")
        end_position, step_count = game_module.advance_reel_to_position(
            strip,
            start_position=0,
            target_position=2,
            min_steps=6,
        )
        self.assertEqual(end_position, 2)
        self.assertEqual(strip[end_position], "SLOT_2")
        self.assertGreaterEqual(step_count, 6)


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

    def test_spin_result_for_again_spins_and_uses_loss_multiplier(self) -> None:
        config = make_config(answer_base_values={"again": -1})
        strip = game_module.build_reel_strip(config)
        reel_positions = (
            strip.index("SLOT_2"),
            strip.index("SLOT_5"),
            strip.index("SLOT_2"),
        )
        with patch.object(
            game_module,
            "spin_reel_positions",
            return_value=reel_positions,
        ):
            result = game_module.build_spin_result(
                config,
                card_id=42,
                answer_key="again",
                bet=Decimal("1.00"),
                balance_before=Decimal("100.00"),
                rng=random.Random(2),
            )
        self.assertFalse(result.is_win)
        self.assertTrue(result.did_spin)
        self.assertTrue(result.animation_enabled)
        self.assertEqual(result.reels, ("SLOT_2", "SLOT_5", "SLOT_2"))
        self.assertEqual(result.base_reward, Decimal("-1.00"))
        self.assertEqual(result.matched_symbol, "SLOT_2")
        self.assertEqual(
            result.slot_multiplier,
            config.slot_double_multipliers["SLOT_2"],
        )
        self.assertEqual(result.payout, Decimal("-0.95"))
        self.assertEqual(result.net_change, result.payout)
        self.assertEqual(result.balance_after, Decimal("100.00") + result.payout)

    def test_spin_result_for_again_cannot_take_balance_below_zero(self) -> None:
        config = make_config(answer_base_values={"again": -1})
        strip = game_module.build_reel_strip(config)
        reel_positions = (
            strip.index("SLOT_4"),
            strip.index("SLOT_4"),
            strip.index("SLOT_4"),
        )
        with patch.object(
            game_module,
            "spin_reel_positions",
            return_value=reel_positions,
        ):
            result = game_module.build_spin_result(
                config,
                card_id=42,
                answer_key="again",
                bet=Decimal("1.00"),
                balance_before=Decimal("1.50"),
                rng=random.Random(2),
            )
        self.assertEqual(result.payout, Decimal("-1.50"))
        self.assertEqual(result.net_change, Decimal("-1.50"))
        self.assertEqual(result.balance_after, Decimal("0.00"))

    def test_spin_result_for_again_with_zero_base_does_not_spin(self) -> None:
        config = make_config(answer_base_values={"again": 0})
        result = game_module.build_spin_result(
            config,
            card_id=42,
            answer_key="again",
            bet=Decimal("1.00"),
            balance_before=Decimal("100.00"),
            rng=random.Random(2),
        )

        self.assertFalse(result.did_spin)
        self.assertTrue(result.no_spin)
        self.assertEqual(result.base_reward, Decimal("0.00"))
        self.assertEqual(result.payout, Decimal("0.00"))
        self.assertEqual(result.reel_step_counts, (0, 0, 0))

    def test_spin_result_for_again_without_spin_override_is_a_no_op(self) -> None:
        config = make_config(answer_base_values={"again": -1})
        previous_positions = (0, 35, 60)
        result = game_module.build_spin_result(
            config,
            card_id=42,
            answer_key="again",
            bet=Decimal("1.00"),
            balance_before=Decimal("100.00"),
            rng=random.Random(2),
            previous_reel_positions=previous_positions,
            did_spin_override=False,
        )

        self.assertFalse(result.did_spin)
        self.assertTrue(result.no_spin)
        self.assertEqual(result.base_reward, Decimal("-1.00"))
        self.assertEqual(result.payout, Decimal("0.00"))
        self.assertEqual(result.reel_positions, previous_positions)
        self.assertEqual(result.reel_step_counts, (0, 0, 0))

    def test_spin_result_for_hard_is_neutral_when_configured_to_zero(self) -> None:
        config = make_config(answer_base_values={"hard": 0})
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
        self.assertTrue(result.no_spin)
        self.assertEqual(result.base_reward, Decimal("0.00"))
        self.assertEqual(result.slot_bonus, Decimal("0.00"))
        self.assertIsNone(result.matched_symbol)

    def test_spin_result_for_hard_uses_default_positive_base_value(self) -> None:
        config = make_config()
        strip = game_module.build_reel_strip(config)
        reel_positions = (
            strip.index("SLOT_2"),
            strip.index("SLOT_5"),
            strip.index("SLOT_2"),
        )
        with patch.object(
            game_module,
            "spin_reel_positions",
            return_value=reel_positions,
        ):
            result = game_module.build_spin_result(
                config,
                card_id=42,
                answer_key="hard",
                bet=Decimal("1.00"),
                balance_before=Decimal("100.00"),
                rng=random.Random(2),
            )

        self.assertTrue(result.did_spin)
        self.assertEqual(result.base_reward, Decimal("0.50"))
        self.assertEqual(result.payout, Decimal("0.48"))
        self.assertEqual(result.balance_after, Decimal("100.48"))

    def test_spin_result_for_hard_uses_configured_signed_base_value(self) -> None:
        config = make_config(answer_base_values={"hard": -0.5})
        strip = game_module.build_reel_strip(config)
        reel_positions = (
            strip.index("SLOT_2"),
            strip.index("SLOT_5"),
            strip.index("SLOT_2"),
        )
        with patch.object(
            game_module,
            "spin_reel_positions",
            return_value=reel_positions,
        ):
            result = game_module.build_spin_result(
                config,
                card_id=42,
                answer_key="hard",
                bet=Decimal("1.00"),
                balance_before=Decimal("100.00"),
                rng=random.Random(2),
            )

        self.assertTrue(result.did_spin)
        self.assertEqual(result.base_reward, Decimal("-0.50"))
        self.assertEqual(result.payout, Decimal("-0.48"))
        self.assertEqual(result.balance_after, Decimal("99.52"))

    def test_spin_result_without_spin_preserves_reel_positions(self) -> None:
        config = make_config()
        previous_positions = (0, 35, 60)
        result = game_module.build_spin_result(
            config,
            card_id=42,
            answer_key="hard",
            bet=Decimal("1.00"),
            balance_before=Decimal("100.00"),
            rng=random.Random(2),
            previous_reel_positions=previous_positions,
            did_spin_override=False,
        )
        self.assertEqual(result.reel_start_positions, previous_positions)
        self.assertEqual(result.reel_positions, previous_positions)
        self.assertEqual(result.reel_step_counts, (0, 0, 0))
        self.assertEqual(result.base_reward, Decimal("0.50"))
        self.assertEqual(result.payout, Decimal("0.00"))
        self.assertEqual(
            result.reels,
            game_module.visible_reels_for_positions(config, previous_positions),
        )

    def test_spin_result_for_good_uses_triple_multiplier(self) -> None:
        config = make_config()
        strip = game_module.build_reel_strip(config)
        reel_positions = (
            strip.index("SLOT_3"),
            strip.index("SLOT_3"),
            strip.index("SLOT_3"),
        )
        with patch.object(
            game_module,
            "spin_reel_positions",
            return_value=reel_positions,
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
        strip = game_module.build_reel_strip(config)
        reel_positions = (
            strip.index("SLOT_2"),
            strip.index("SLOT_5"),
            strip.index("SLOT_2"),
        )
        with patch.object(
            game_module,
            "spin_reel_positions",
            return_value=reel_positions,
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
        strip = game_module.build_reel_strip(config)
        reel_positions = (
            strip.index("SLOT_1"),
            strip.index("SLOT_3"),
            strip.index("SLOT_2"),
        )
        with patch.object(
            game_module,
            "spin_reel_positions",
            return_value=reel_positions,
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

    def test_spin_result_for_good_can_be_negative_when_configured(self) -> None:
        config = make_config(answer_base_values={"good": -1})
        strip = game_module.build_reel_strip(config)
        reel_positions = (
            strip.index("SLOT_2"),
            strip.index("SLOT_5"),
            strip.index("SLOT_2"),
        )
        with patch.object(
            game_module,
            "spin_reel_positions",
            return_value=reel_positions,
        ):
            result = game_module.build_spin_result(
                config,
                card_id=42,
                answer_key="good",
                bet=Decimal("1.00"),
                balance_before=Decimal("100.00"),
                rng=random.Random(2),
            )

        self.assertEqual(result.base_reward, Decimal("-1.00"))
        self.assertEqual(result.payout, Decimal("-0.95"))
        self.assertFalse(result.is_win)

    def test_spin_result_for_good_with_zero_base_does_not_spin(self) -> None:
        config = make_config(answer_base_values={"good": 0})
        result = game_module.build_spin_result(
            config,
            card_id=42,
            answer_key="good",
            bet=Decimal("1.00"),
            balance_before=Decimal("100.00"),
            rng=random.Random(2),
        )

        self.assertFalse(result.did_spin)
        self.assertEqual(result.base_reward, Decimal("0.00"))
        self.assertEqual(result.payout, Decimal("0.00"))

    def test_spin_result_tracks_reel_positions_for_real_rotation(self) -> None:
        config = make_config()
        previous_positions = (0, 35, 60)
        strip = game_module.build_reel_strip(config)
        reel_positions = (
            strip.index("SLOT_2"),
            strip.index("SLOT_5"),
            strip.index("SLOT_2"),
        )
        with patch.object(
            game_module,
            "spin_reel_positions",
            return_value=reel_positions,
        ):
            result = game_module.build_spin_result(
                config,
                card_id=42,
                answer_key="good",
                bet=Decimal("1.00"),
                balance_before=Decimal("100.00"),
                rng=random.Random(2),
                previous_reel_positions=previous_positions,
            )
        self.assertEqual(result.reel_start_positions, previous_positions)
        self.assertTrue(all(step_count > 0 for step_count in result.reel_step_counts))
        self.assertEqual(
            game_module.visible_reels_for_positions(config, result.reel_positions),
            result.reels,
        )

    def test_spin_result_for_easy_uses_default_base_times_multiplier(self) -> None:
        config = make_config()
        strip = game_module.build_reel_strip(config)
        reel_positions = (
            strip.index("SLOT_4"),
            strip.index("SLOT_4"),
            strip.index("SLOT_4"),
        )
        with patch.object(
            game_module,
            "spin_reel_positions",
            return_value=reel_positions,
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
        self.assertEqual(result.base_reward, Decimal("1.50"))
        self.assertEqual(
            result.payout,
            (Decimal("1.50") * config.slot_triple_multipliers["SLOT_4"]).quantize(
                Decimal("0.01")
            ),
        )
        self.assertEqual(result.balance_after, Decimal("100.00") + result.payout)
        self.assertTrue(result.animation_enabled)


if __name__ == "__main__":
    unittest.main()
