#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROFILE_PATH = (
    ROOT / "src" / "anki_slot_machine" / "slot_profiles" / "base.json"
)


def to_decimal(value) -> Decimal:
    return Decimal(str(value))


def fmt_decimal(value: Decimal, places: int = 4) -> str:
    quant = Decimal("1").scaleb(-places)
    return f"{value.quantize(quant):.{places}f}"


def fmt_percent(value: Decimal, places: int = 2) -> str:
    return f"{fmt_decimal(value * Decimal('100'), places)}%"


def fmt_one_in(value: Decimal, places: int = 1) -> str:
    if value <= 0:
        return "never"
    inverse = Decimal("1") / value
    return f"1 in {fmt_decimal(inverse, places)}"


@dataclass(frozen=True)
class SymbolStats:
    symbol: str
    faces: int
    reel_probability: Decimal
    exact_pair_probability: Decimal
    triple_probability: Decimal
    pair_multiplier: Decimal
    triple_multiplier: Decimal

    @property
    def pair_ev(self) -> Decimal:
        return self.exact_pair_probability * self.pair_multiplier

    @property
    def triple_ev(self) -> Decimal:
        return self.triple_probability * self.triple_multiplier


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate a real 3-reel slot from face counts and pair/triple gains.",
    )
    parser.add_argument(
        "--profile",
        type=Path,
        default=DEFAULT_PROFILE_PATH,
        help="Optional JSON profile with faces and multipliers.",
    )
    parser.add_argument(
        "--face",
        action="append",
        default=[],
        metavar="SLOT_N=COUNT",
        help="Override one face count. Can be repeated.",
    )
    parser.add_argument(
        "--pair",
        action="append",
        default=[],
        metavar="SLOT_N=MULTIPLIER",
        help="Override one exact-pair multiplier. Can be repeated.",
    )
    parser.add_argument(
        "--triple",
        action="append",
        default=[],
        metavar="SLOT_N=MULTIPLIER",
        help="Override one triple multiplier. Can be repeated.",
    )
    return parser.parse_args()


def load_profile(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_mapping(items: list[str], *, integer: bool) -> dict[str, int | Decimal]:
    mapping: dict[str, int | Decimal] = {}
    for item in items:
        key, value = item.split("=", 1)
        symbol = key.strip().upper()
        mapping[symbol] = int(value) if integer else to_decimal(value)
    return mapping


def merged_inputs(args: argparse.Namespace) -> tuple[str, dict[str, int], dict[str, Decimal], dict[str, Decimal]]:
    raw = load_profile(args.profile)
    name = str(raw.get("name") or args.profile.stem)
    faces = {
        str(key).upper(): int(value)
        for key, value in (raw.get("faces") or {}).items()
    }
    pair = {
        str(key).upper(): to_decimal(value)
        for key, value in (raw.get("pair_multipliers") or {}).items()
    }
    triple = {
        str(key).upper(): to_decimal(value)
        for key, value in (raw.get("triple_multipliers") or {}).items()
    }
    faces.update(parse_mapping(args.face, integer=True))
    pair.update(parse_mapping(args.pair, integer=False))
    triple.update(parse_mapping(args.triple, integer=False))
    return name, faces, pair, triple


def ordered_symbols(faces: dict[str, int], pair: dict[str, Decimal], triple: dict[str, Decimal]) -> list[str]:
    symbols = sorted(set(faces) | set(pair) | set(triple))
    return sorted(symbols, key=lambda symbol: int(symbol.rsplit("_", 1)[-1]))


def validate(faces: dict[str, int], pair: dict[str, Decimal], triple: dict[str, Decimal]) -> list[str]:
    issues: list[str] = []
    total_faces = sum(max(0, count) for count in faces.values())
    if total_faces <= 0:
        issues.append("At least one face count must be greater than zero.")
    for symbol, count in faces.items():
        if count < 0:
            issues.append(f"{symbol} has a negative face count.")
    for symbol in ordered_symbols(faces, pair, triple):
        if symbol not in pair:
            issues.append(f"{symbol} is missing a pair multiplier.")
        if symbol not in triple:
            issues.append(f"{symbol} is missing a triple multiplier.")
    return issues


def build_stats(
    faces: dict[str, int],
    pair: dict[str, Decimal],
    triple: dict[str, Decimal],
) -> tuple[list[SymbolStats], Decimal, Decimal, Decimal, Decimal]:
    total_faces = sum(max(0, count) for count in faces.values())
    total_faces_dec = Decimal(total_faces)
    stats: list[SymbolStats] = []
    total_pair = Decimal("0")
    total_triple = Decimal("0")
    ev = Decimal("0")

    for symbol in ordered_symbols(faces, pair, triple):
        p = Decimal(max(0, faces.get(symbol, 0))) / total_faces_dec
        pair_p = Decimal("3") * (p ** 2) * (Decimal("1") - p)
        triple_p = p ** 3
        entry = SymbolStats(
            symbol=symbol,
            faces=max(0, faces.get(symbol, 0)),
            reel_probability=p,
            exact_pair_probability=pair_p,
            triple_probability=triple_p,
            pair_multiplier=pair[symbol],
            triple_multiplier=triple[symbol],
        )
        stats.append(entry)
        total_pair += pair_p
        total_triple += triple_p
        ev += entry.pair_ev + entry.triple_ev

    no_match = Decimal("1") - total_pair - total_triple
    return stats, total_pair, total_triple, no_match, ev


def conditional_ev(hit_rate: Decimal, ev: Decimal) -> Decimal:
    if hit_rate <= 0:
        return Decimal("0")
    return ev / hit_rate


def variance(stats: list[SymbolStats], mean: Decimal, no_match: Decimal) -> Decimal:
    total = no_match * ((Decimal("0") - mean) ** 2)
    for entry in stats:
        total += entry.exact_pair_probability * ((entry.pair_multiplier - mean) ** 2)
        total += entry.triple_probability * ((entry.triple_multiplier - mean) ** 2)
    return total


def report(
    name: str,
    faces: dict[str, int],
    pair: dict[str, Decimal],
    triple: dict[str, Decimal],
) -> str:
    stats, total_pair, total_triple, no_match, ev = build_stats(faces, pair, triple)
    hit_rate = Decimal("1") - no_match
    hit_ev = conditional_ev(hit_rate, ev)
    stdev = variance(stats, ev, no_match).sqrt()

    lines = [
        "Real Slot Report",
        "================",
        f"Profile: {name}",
        "",
        "Core metrics",
        "------------",
        f"Total faces: {sum(faces.values())}",
        f"No-match probability: {fmt_percent(no_match, 4)} ({fmt_one_in(no_match)})",
        f"Any exact pair probability: {fmt_percent(total_pair, 4)} ({fmt_one_in(total_pair)})",
        f"Any triple probability: {fmt_percent(total_triple, 4)} ({fmt_one_in(total_triple)})",
        f"Any hit probability: {fmt_percent(hit_rate, 4)} ({fmt_one_in(hit_rate)})",
        f"Expected multiplier per spin: x{fmt_decimal(ev, 4)}",
        f"Expected multiplier conditional on hit: x{fmt_decimal(hit_ev, 4)}",
        f"Multiplier standard deviation: {fmt_decimal(stdev, 4)}",
        "",
        "Per-symbol breakdown",
        "--------------------",
    ]

    for entry in stats:
        lines.extend(
            [
                f"{entry.symbol} ({entry.faces} faces)",
                f"  Reel probability: {fmt_percent(entry.reel_probability, 4)}",
                (
                    f"  Exact pair: {fmt_percent(entry.exact_pair_probability, 4)}"
                    f" ({fmt_one_in(entry.exact_pair_probability)})"
                    f" -> x{fmt_decimal(entry.pair_multiplier, 2)}"
                    f" | EV+ {fmt_decimal(entry.pair_ev, 4)}"
                ),
                (
                    f"  Triple: {fmt_percent(entry.triple_probability, 4)}"
                    f" ({fmt_one_in(entry.triple_probability)})"
                    f" -> x{fmt_decimal(entry.triple_multiplier, 2)}"
                    f" | EV+ {fmt_decimal(entry.triple_ev, 4)}"
                ),
                "",
            ]
        )
    if lines[-1] == "":
        lines.pop()

    lines.extend(
        [
            "",
            "Top EV contributors",
            "-------------------",
        ]
    )

    contributions: list[tuple[str, Decimal]] = []
    for entry in stats:
        contributions.append((f"{entry.symbol} pair", entry.pair_ev))
        contributions.append((f"{entry.symbol} triple", entry.triple_ev))
    for label, contribution in sorted(contributions, key=lambda item: item[1], reverse=True)[:8]:
        share = Decimal("0") if ev == 0 else contribution / ev
        lines.append(
            f"{label:<16} -> {fmt_decimal(contribution, 4)} "
            f"({fmt_percent(share, 2)} of EV)"
        )

    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    name, faces, pair, triple = merged_inputs(args)
    issues = validate(faces, pair, triple)
    if issues:
        print("Input validation issues")
        print("=======================")
        for issue in issues:
            print(f"- {issue}")
        return 1

    print(report(name, faces, pair, triple))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
