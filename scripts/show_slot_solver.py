#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from anki_slot_machine.config import config_from_raw
from anki_slot_machine.decimal_utils import format_decimal


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = ROOT / "src" / "anki_slot_machine" / "config.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Explain how the slot EV solver derives pair/triple multipliers.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Path to a config.json file.",
    )
    parser.add_argument(
        "--expected-multiplier-target",
        type=float,
        help="Override the target expected multiplier.",
    )
    parser.add_argument(
        "--decimal-places",
        type=int,
        help="Override decimal precision.",
    )
    parser.add_argument(
        "--rarity-exponent",
        type=float,
        help="Override the non-linear rarity exponent used for reward shaping.",
    )
    parser.add_argument(
        "--triple-scale-multiplier",
        type=float,
        help="Override how much stronger triples scale than pairs.",
    )
    parser.add_argument(
        "--pair-scale-multiplier",
        type=float,
        help="Override how much strongly pairs scale everywhere.",
    )
    parser.add_argument(
        "--slot-face",
        action="append",
        default=[],
        metavar="SLOT_N=COUNT",
        help="Override one slot face count. Can be repeated.",
    )
    return parser.parse_args()


def load_raw_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def apply_overrides(raw: dict, args: argparse.Namespace) -> dict:
    updated = dict(raw)
    if args.expected_multiplier_target is not None:
        updated["expected_multiplier_target"] = args.expected_multiplier_target
    if args.decimal_places is not None:
        updated["decimal_places"] = args.decimal_places
    if args.rarity_exponent is not None:
        updated["rarity_exponent"] = args.rarity_exponent
    if args.pair_scale_multiplier is not None:
        updated["pair_scale_multiplier"] = args.pair_scale_multiplier
    if args.triple_scale_multiplier is not None:
        updated["triple_scale_multiplier"] = args.triple_scale_multiplier
    if args.slot_face:
        slot_faces = dict(updated.get("slot_faces") or {})
        for item in args.slot_face:
            name, value = item.split("=", 1)
            slot_faces[name.strip().upper()] = int(value)
        updated["slot_faces"] = slot_faces
    return updated


def explain_low_multiplier(summary, decimal_places: int) -> str:
    event_mass = summary.total_double_probability + summary.total_triple_probability
    return (
        "Low multipliers usually mean the EV target is low while pair/triple "
        f"events are common enough to consume most of the reward mass. Here, pair+triple "
        f"probability is {format_decimal(event_mass * 100, decimal_places)}%."
    )


def main() -> int:
    args = parse_args()
    raw = apply_overrides(load_raw_config(args.config), args)
    config = config_from_raw(raw)
    summary = config.slot_probability_summary

    print("Slot Solver Report")
    print("==================")
    print(f"Config: {args.config}")
    print(f"Starting balance: {format_decimal(config.starting_balance, config.decimal_places)}")
    print(f"Target expected multiplier: x{format_decimal(summary.target_expected_multiplier, config.decimal_places)}")
    print(f"Achieved expected multiplier: x{format_decimal(summary.achieved_expected_multiplier, config.decimal_places)}")
    print(f"Decimal places: {config.decimal_places}")
    print(f"Rarity exponent: {format_decimal(summary.rarity_exponent, 4)}")
    print(f"Pair scale multiplier: {format_decimal(summary.pair_scale_multiplier, 4)}")
    print(f"Triple scale multiplier: {format_decimal(summary.triple_scale_multiplier, 4)}")
    print(f"Scale a (double): {format_decimal(summary.scale_a, 6)}")
    print(f"Scale b (triple): {format_decimal(summary.scale_b, 6)}")
    print(f"Solver denominator: {format_decimal(summary.denominator, 6)}")
    print(f"No-match probability: {format_decimal(summary.no_match_probability * 100, 4)}%")
    print(f"Any pair probability: {format_decimal(summary.total_double_probability * 100, 4)}%")
    print(f"Any triple probability: {format_decimal(summary.total_triple_probability * 100, 4)}%")
    print(f"Expected Good payout: ${format_decimal(summary.expected_good_payout, config.decimal_places)}")
    print(f"Expected Easy payout: ${format_decimal(summary.expected_easy_payout, config.decimal_places)}")
    print()
    print("How it is computed")
    print("------------------")
    print("1. p = faces / total_faces")
    print("2. score = (-log(p)) ^ rarity_exponent")
    print("3. P(double) = 3 * p^2 * (1 - p)")
    print("4. P(triple) = p^3")
    print("5. no-match multiplier = 0")
    print("6. double = 1 + score * a * pair_scale_multiplier")
    print("7. triple = 1 + score * a * triple_scale_multiplier")
    print("8. round to decimal_places and recompute achieved EV")
    print()
    print(explain_low_multiplier(summary, 4))
    print()
    print("Per-symbol breakdown")
    print("--------------------")
    header = (
        f"{'Symbol':<8} {'Faces':>5} {'p':>8} {'Score':>8} "
        f"{'P2':>8} {'Raw x2':>9} {'x2':>7} "
        f"{'P3':>8} {'Raw x3':>9} {'x3':>7}"
    )
    print(header)
    print("-" * len(header))
    for odds in summary.symbol_odds:
        print(
            f"{odds.symbol:<8} "
            f"{odds.faces:>5} "
            f"{format_decimal(odds.single_probability, 4):>8} "
            f"{format_decimal(odds.score, 4):>8} "
            f"{format_decimal(odds.double_probability, 4):>8} "
            f"{format_decimal(odds.raw_double_multiplier, 4):>9} "
            f"{format_decimal(odds.double_multiplier, config.decimal_places):>7} "
            f"{format_decimal(odds.triple_probability, 4):>8} "
            f"{format_decimal(odds.raw_triple_multiplier, 4):>9} "
            f"{format_decimal(odds.triple_multiplier, config.decimal_places):>7}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
