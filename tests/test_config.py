from __future__ import annotations

import copy
import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from test_support import install_stubs

install_stubs()

import anki_slot_machine.config as config_module
from anki_slot_machine.decimal_utils import quantize_decimal


def build_profile(**overrides) -> dict:
    profile = copy.deepcopy(config_module.DEFAULT_SLOT_PROFILE)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(profile.get(key), dict):
            profile[key] = {**profile[key], **value}
        else:
            profile[key] = value
    return profile


def load_test_config(*, profile_overrides=None, **config_overrides):
    profile = build_profile(**(profile_overrides or {}))
    raw = {
        "starting_balance": 100,
        "decimal_places": 2,
    }
    raw.update(config_overrides)
    with tempfile.TemporaryDirectory() as tmp_dir:
        profile_path = Path(tmp_dir) / "profile.json"
        profile_path.write_text(json.dumps(profile), encoding="utf-8")
        raw["slot_profile_path"] = str(profile_path)
        return config_module.config_from_raw(raw)


class ConfigProfileTests(unittest.TestCase):
    def test_machine_list_uses_one_shared_profile_for_all_windows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            shared_profile_path = Path(tmp_dir) / "shared.json"
            shared_profile_path.write_text(
                json.dumps(
                    build_profile(
                        name="shared_floor",
                        pair_multipliers={"SLOT_5": 9.75},
                    )
                ),
                encoding="utf-8",
            )
            config = config_module.config_from_raw(
                {
                    "starting_balance": 100,
                    "decimal_places": 2,
                    "slot_profile_path": str(shared_profile_path),
                    "machines": [
                        {
                            "key": "alpha",
                            "label": "Alpha Floor",
                        },
                        {
                            "key": "beta",
                            "label": "Beta Floor",
                        },
                    ],
                }
            )

        self.assertEqual(config.machine_count, 2)
        self.assertEqual(config.machines[0].key, "alpha")
        self.assertEqual(config.machines[1].key, "beta")
        self.assertEqual(config.slot_profile_name, "shared_floor")
        self.assertEqual(config.slot_profile_path, str(shared_profile_path))
        self.assertEqual(config.machines[0].slot_profile_path, str(shared_profile_path))
        self.assertEqual(config.machines[1].slot_profile_path, str(shared_profile_path))
        self.assertEqual(config.machines[0].slot_profile_name, "shared_floor")
        self.assertEqual(config.machines[1].slot_profile_name, "shared_floor")
        self.assertEqual(config.machines[1].slot_double_multipliers["SLOT_5"], Decimal("9.75"))

    def test_probabilities_match_slot_faces(self) -> None:
        config = load_test_config(
            profile_overrides={
                "faces": {
                    "SLOT_1": 8,
                    "SLOT_2": 5,
                    "SLOT_3": 3,
                    "SLOT_4": 2,
                    "SLOT_5": 2,
                }
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

    def test_profile_pair_and_triple_tables_are_loaded(self) -> None:
        config = load_test_config(
            profile_overrides={
                "pair_multipliers": {"SLOT_5": 9.75},
                "triple_multipliers": {"SLOT_5": 88.88},
            }
        )
        self.assertEqual(config.slot_double_multipliers["SLOT_5"], Decimal("9.75"))
        self.assertEqual(config.slot_triple_multipliers["SLOT_5"], Decimal("88.88"))

    def test_expected_multiplier_is_recomputed_from_profile_tables(self) -> None:
        config = load_test_config()
        summary = config.slot_probability_summary
        expected = Decimal("0")
        for odds in summary.symbol_odds:
            expected += odds.double_probability * odds.double_multiplier
            expected += odds.triple_probability * odds.triple_multiplier
        self.assertEqual(
            quantize_decimal(expected, config.decimal_places),
            summary.expected_multiplier,
        )

    def test_all_zero_faces_fall_back_to_default_profile_faces(self) -> None:
        config = load_test_config(
            profile_overrides={
                "faces": {
                    "SLOT_1": 0,
                    "SLOT_2": 0,
                    "SLOT_3": 0,
                    "SLOT_4": 0,
                    "SLOT_5": 0,
                }
            }
        )
        self.assertEqual(config.slot_faces, config_module.DEFAULT_SLOT_PROFILE["faces"])

    def test_missing_profile_path_falls_back_to_packaged_default_profile(self) -> None:
        config = config_module.config_from_raw(
            {
                "starting_balance": 100,
                "decimal_places": 2,
                "slot_profile_path": "/definitely/missing/profile.json",
            }
        )
        self.assertEqual(config.slot_faces, config_module.DEFAULT_SLOT_PROFILE["faces"])
        self.assertEqual(
            config.slot_probability_summary.profile_name,
            config_module.DEFAULT_SLOT_PROFILE["name"],
        )

    def test_loaded_multipliers_respect_decimal_places(self) -> None:
        config = load_test_config(
            decimal_places=1,
            profile_overrides={
                "pair_multipliers": {"SLOT_2": 1.149},
                "triple_multipliers": {"SLOT_4": 27.777},
            },
        )
        self.assertEqual(config.slot_double_multipliers["SLOT_2"], Decimal("1.1"))
        self.assertEqual(config.slot_triple_multipliers["SLOT_4"], Decimal("27.8"))

    def test_spin_animation_duration_is_loaded_and_clamped(self) -> None:
        self.assertEqual(
            load_test_config(spin_animation_duration_ms=640).spin_animation_duration_ms,
            640,
        )
        self.assertEqual(
            load_test_config(spin_animation_duration_ms=999).spin_animation_duration_ms,
            750,
        )


if __name__ == "__main__":
    unittest.main()
