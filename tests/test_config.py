from __future__ import annotations

import unittest
from decimal import Decimal
from unittest.mock import patch

from test_support import install_stubs

install_stubs()

import anki_slot_machine.config as config_module
from anki_slot_machine.decimal_utils import quantize_decimal


def load_test_config(**overrides):
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
    return config_module.config_from_raw(raw)


class ConfigSolverTests(unittest.TestCase):
    def test_probabilities_match_slot_faces(self) -> None:
        config = load_test_config(
            slot_faces={
                "SLOT_1": 8,
                "SLOT_2": 5,
                "SLOT_3": 3,
                "SLOT_4": 2,
                "SLOT_5": 2,
            }
        )
        odds_by_symbol = {
            odds.symbol: odds
            for odds in config.slot_probability_summary.symbol_odds
        }
        self.assertEqual(odds_by_symbol["SLOT_1"].single_probability, Decimal("0.4"))
        self.assertEqual(odds_by_symbol["SLOT_2"].single_probability, Decimal("0.25"))
        self.assertEqual(odds_by_symbol["SLOT_3"].single_probability, Decimal("0.15"))
        self.assertEqual(odds_by_symbol["SLOT_4"].single_probability, Decimal("0.1"))
        self.assertEqual(odds_by_symbol["SLOT_5"].single_probability, Decimal("0.1"))

    def test_solver_derives_monotonic_double_and_triple_multipliers(self) -> None:
        config = load_test_config()
        ordered = sorted(
            config.slot_probability_summary.symbol_odds,
            key=lambda odds: float(odds.single_probability),
            reverse=True,
        )
        previous_double = Decimal("1")
        previous_triple = Decimal("1")
        for odds in ordered:
            self.assertGreaterEqual(odds.double_multiplier, previous_double)
            self.assertGreater(odds.triple_multiplier, odds.double_multiplier)
            self.assertGreaterEqual(odds.triple_multiplier, previous_triple)
            previous_double = odds.double_multiplier
            previous_triple = odds.triple_multiplier

    def test_achieved_expected_multiplier_is_recomputed_from_rounded_tables(self) -> None:
        config = load_test_config()
        summary = config.slot_probability_summary
        achieved = Decimal("0")
        for odds in summary.symbol_odds:
            achieved += odds.double_probability * odds.double_multiplier
            achieved += odds.triple_probability * odds.triple_multiplier
        self.assertEqual(
            quantize_decimal(achieved, config.decimal_places),
            summary.achieved_expected_multiplier,
        )

    def test_solver_exposes_configurable_aggression_knobs(self) -> None:
        config = load_test_config(
            rarity_exponent=2.0,
            pair_scale_multiplier=0.5,
            triple_scale_multiplier=8,
        )
        summary = config.slot_probability_summary
        self.assertEqual(summary.rarity_exponent, Decimal("2.0"))
        self.assertEqual(summary.pair_scale_multiplier, Decimal("0.5"))
        self.assertEqual(summary.triple_scale_multiplier, Decimal("8"))

    def test_more_aggressive_settings_push_rare_rewards_higher(self) -> None:
        baseline = load_test_config()
        aggressive = load_test_config(
            rarity_exponent=2.0,
            pair_scale_multiplier=0.5,
            triple_scale_multiplier=8,
        )
        baseline_odds = {
            odds.symbol: odds for odds in baseline.slot_probability_summary.symbol_odds
        }
        aggressive_odds = {
            odds.symbol: odds for odds in aggressive.slot_probability_summary.symbol_odds
        }
        self.assertGreater(
            aggressive_odds["SLOT_5"].triple_multiplier,
            baseline_odds["SLOT_5"].triple_multiplier,
        )
        self.assertLessEqual(
            aggressive_odds["SLOT_1"].double_multiplier,
            baseline_odds["SLOT_1"].double_multiplier,
        )

    def test_all_zero_faces_fall_back_to_defaults(self) -> None:
        config = load_test_config(
            slot_faces={
                "SLOT_1": 0,
                "SLOT_2": 0,
                "SLOT_3": 0,
                "SLOT_4": 0,
                "SLOT_5": 0,
            }
        )
        self.assertEqual(config.slot_faces, config_module.DEFAULT_SLOT_FACES)

    def test_target_below_event_floor_uses_minimum_event_multipliers(self) -> None:
        config = load_test_config(expected_multiplier_target=0.00)
        for odds in config.slot_probability_summary.symbol_odds:
            self.assertEqual(odds.double_multiplier, Decimal("1"))
            self.assertEqual(odds.triple_multiplier, Decimal("1"))


if __name__ == "__main__":
    unittest.main()
