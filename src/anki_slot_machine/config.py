from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal

from .decimal_utils import (
    ONE,
    THREE,
    ZERO,
    decimal_places_value,
    quantize_decimal,
    to_decimal,
)

DEFAULT_SLOT_FACES = {
    "SLOT_1": 50,
    "SLOT_2": 28,
    "SLOT_3": 15,
    "SLOT_4": 6,
    "SLOT_5": 1,
}
DEFAULT_HISTORY_LIMIT = 30
DEFAULT_MILESTONE_THRESHOLDS = (250, 500, 1000, 2500)
DEFAULT_EXPECTED_MULTIPLIER_TARGET = Decimal("1.10")
DEFAULT_DECIMAL_PLACES = 2
DEFAULT_RARITY_EXPONENT = Decimal("1.6")
DEFAULT_PAIR_SCALE_MULTIPLIER = Decimal("1")
DEFAULT_TRIPLE_SCALE_MULTIPLIER = Decimal("6")


@dataclass(frozen=True)
class SlotSymbolOdds:
    symbol: str
    faces: int
    single_probability: Decimal
    double_probability: Decimal
    triple_probability: Decimal
    score: Decimal
    raw_double_multiplier: Decimal
    raw_triple_multiplier: Decimal
    double_multiplier: Decimal
    triple_multiplier: Decimal


@dataclass(frozen=True)
class SlotProbabilitySummary:
    target_expected_multiplier: Decimal
    achieved_expected_multiplier: Decimal
    rarity_exponent: Decimal
    pair_scale_multiplier: Decimal
    scale_a: Decimal
    scale_b: Decimal
    triple_scale_multiplier: Decimal
    denominator: Decimal
    symbol_odds: tuple[SlotSymbolOdds, ...]
    total_double_probability: Decimal
    total_triple_probability: Decimal
    no_match_probability: Decimal
    expected_good_payout: Decimal
    expected_easy_payout: Decimal


@dataclass(frozen=True)
class SlotMachineConfig:
    starting_balance: Decimal
    expected_multiplier_target: Decimal
    decimal_places: int
    rarity_exponent: Decimal
    pair_scale_multiplier: Decimal
    triple_scale_multiplier: Decimal
    slot_faces: dict[str, int]
    slot_double_multipliers: dict[str, Decimal]
    slot_triple_multipliers: dict[str, Decimal]
    slot_probability_summary: SlotProbabilitySummary
    history_limit: int
    milestone_thresholds: tuple[int, ...]


def _sort_key(symbol: str) -> tuple[int, str]:
    suffix = symbol.rsplit("_", 1)[-1]
    if suffix.isdigit():
        return int(suffix), symbol
    return 10_000, symbol


def _sorted_slot_symbols(source: dict[str, int]) -> tuple[str, ...]:
    return tuple(sorted(source.keys(), key=_sort_key)) or ("SLOT_1",)


def _load_slot_faces(raw: dict | None) -> dict[str, int]:
    source = raw if isinstance(raw, dict) else {}
    faces: dict[str, int] = {}
    for key, default_value in DEFAULT_SLOT_FACES.items():
        try:
            faces[key] = max(0, int(source.get(key, default_value)))
        except (TypeError, ValueError):
            faces[key] = default_value
    if any(value > 0 for value in faces.values()):
        return faces
    return dict(DEFAULT_SLOT_FACES)


def _load_target_expected_multiplier(raw_value) -> Decimal:
    return max(
        ZERO,
        to_decimal(raw_value, DEFAULT_EXPECTED_MULTIPLIER_TARGET),
    )


def _load_rarity_exponent(raw_value) -> Decimal:
    return max(
        Decimal("1"),
        to_decimal(raw_value, DEFAULT_RARITY_EXPONENT),
    )


def _load_triple_scale_multiplier(raw_value) -> Decimal:
    return max(
        ONE,
        to_decimal(raw_value, DEFAULT_TRIPLE_SCALE_MULTIPLIER),
    )


def _load_pair_scale_multiplier(raw_value) -> Decimal:
    return max(
        ZERO,
        to_decimal(raw_value, DEFAULT_PAIR_SCALE_MULTIPLIER),
    )


def _score_for_probability(probability: Decimal, rarity_exponent: Decimal) -> Decimal:
    if probability <= ZERO:
        return ZERO
    surprisal = -math.log(float(probability))
    return Decimal(str(surprisal ** float(rarity_exponent)))


def _derive_slot_tables(
    slot_faces: dict[str, int],
    *,
    target_expected_multiplier: Decimal,
    decimal_places: int,
    rarity_exponent: Decimal,
    pair_scale_multiplier: Decimal,
    triple_scale_multiplier: Decimal,
) -> tuple[dict[str, Decimal], dict[str, Decimal], SlotProbabilitySummary]:
    symbols = _sorted_slot_symbols(slot_faces)
    total_faces = sum(max(0, slot_faces.get(symbol, 0)) for symbol in symbols)
    if total_faces <= 0:
        total_faces = sum(DEFAULT_SLOT_FACES.values())
        slot_faces = dict(DEFAULT_SLOT_FACES)
        symbols = _sorted_slot_symbols(slot_faces)

    total_faces_decimal = Decimal(total_faces)
    probabilities = {
        symbol: Decimal(slot_faces.get(symbol, 0)) / total_faces_decimal
        for symbol in symbols
    }
    double_probabilities = {
        symbol: THREE * (probability**2) * (ONE - probability)
        for symbol, probability in probabilities.items()
    }
    triple_probabilities = {
        symbol: probability**3 for symbol, probability in probabilities.items()
    }
    scores = {
        symbol: _score_for_probability(probability, rarity_exponent)
        for symbol, probability in probabilities.items()
    }
    total_double_probability = sum(double_probabilities.values(), ZERO)
    total_triple_probability = sum(triple_probabilities.values(), ZERO)
    event_mass = total_double_probability + total_triple_probability

    denominator = sum(
        (
            double_probabilities[symbol] * scores[symbol] * pair_scale_multiplier
            + (triple_probabilities[symbol] * scores[symbol] * triple_scale_multiplier)
        )
        for symbol in symbols
    )
    use_minimum_tables = target_expected_multiplier <= event_mass or denominator <= ZERO

    raw_double_multipliers = {symbol: ONE for symbol in symbols}
    raw_triple_multipliers = {symbol: ONE for symbol in symbols}

    if not use_minimum_tables:
        scale = (target_expected_multiplier - event_mass) / denominator
        for symbol in symbols:
            if slot_faces.get(symbol, 0) <= 0:
                continue
            score = scores[symbol]
            raw_double_multipliers[symbol] = ONE + (
                score * scale * pair_scale_multiplier
            )
            raw_triple_multipliers[symbol] = ONE + (
                score * scale * triple_scale_multiplier
            )
    else:
        scale = ZERO

    double_multipliers = {symbol: ONE for symbol in symbols}
    triple_multipliers = {symbol: ONE for symbol in symbols}

    if not use_minimum_tables:
        quantum = Decimal("1").scaleb(-decimal_places) if decimal_places else ONE
        ordered_symbols = sorted(
            (symbol for symbol in symbols if slot_faces.get(symbol, 0) > 0),
            key=lambda symbol: (-float(probabilities[symbol]), _sort_key(symbol)),
        )
        previous_double = ONE
        previous_triple = ONE
        for symbol in ordered_symbols:
            double_value = max(
                previous_double,
                quantize_decimal(raw_double_multipliers[symbol], decimal_places),
            )
            triple_value = max(
                previous_triple,
                quantize_decimal(raw_triple_multipliers[symbol], decimal_places),
                double_value + quantum,
            )
            double_multipliers[symbol] = double_value
            triple_multipliers[symbol] = triple_value
            previous_double = double_value
            previous_triple = triple_value

    no_match_probability = max(
        ZERO,
        ONE - total_double_probability - total_triple_probability,
    )
    achieved_expected_multiplier_raw = ZERO
    for symbol in symbols:
        achieved_expected_multiplier_raw += (
            double_probabilities[symbol] * double_multipliers[symbol]
        )
        achieved_expected_multiplier_raw += (
            triple_probabilities[symbol] * triple_multipliers[symbol]
        )

    achieved_expected_multiplier = quantize_decimal(
        achieved_expected_multiplier_raw,
        decimal_places,
    )
    expected_good_payout = quantize_decimal(
        achieved_expected_multiplier,
        decimal_places,
    )
    expected_easy_payout = quantize_decimal(
        achieved_expected_multiplier * Decimal("2"),
        decimal_places,
    )

    symbol_odds = tuple(
        SlotSymbolOdds(
            symbol=symbol,
            faces=slot_faces.get(symbol, 0),
            single_probability=probabilities[symbol],
            double_probability=double_probabilities[symbol],
            triple_probability=triple_probabilities[symbol],
            score=scores[symbol],
            raw_double_multiplier=raw_double_multipliers[symbol],
            raw_triple_multiplier=raw_triple_multipliers[symbol],
            double_multiplier=double_multipliers[symbol],
            triple_multiplier=triple_multipliers[symbol],
        )
        for symbol in symbols
    )
    summary = SlotProbabilitySummary(
        target_expected_multiplier=target_expected_multiplier,
        achieved_expected_multiplier=achieved_expected_multiplier,
        rarity_exponent=rarity_exponent,
        pair_scale_multiplier=pair_scale_multiplier,
        scale_a=scale,
        scale_b=scale * triple_scale_multiplier,
        triple_scale_multiplier=triple_scale_multiplier,
        denominator=denominator,
        symbol_odds=symbol_odds,
        total_double_probability=total_double_probability,
        total_triple_probability=total_triple_probability,
        no_match_probability=no_match_probability,
        expected_good_payout=expected_good_payout,
        expected_easy_payout=expected_easy_payout,
    )
    return double_multipliers, triple_multipliers, summary


def config_from_raw(raw: dict | None) -> SlotMachineConfig:
    raw = raw or {}
    decimal_places = decimal_places_value(
        raw.get("decimal_places"),
        DEFAULT_DECIMAL_PLACES,
    )
    slot_faces = _load_slot_faces(raw.get("slot_faces"))
    target_expected_multiplier = _load_target_expected_multiplier(
        raw.get("expected_multiplier_target"),
    )
    rarity_exponent = _load_rarity_exponent(raw.get("rarity_exponent"))
    pair_scale_multiplier = _load_pair_scale_multiplier(
        raw.get("pair_scale_multiplier")
    )
    triple_scale_multiplier = _load_triple_scale_multiplier(
        raw.get("triple_scale_multiplier")
    )
    slot_double_multipliers, slot_triple_multipliers, probability_summary = (
        _derive_slot_tables(
            slot_faces,
            target_expected_multiplier=target_expected_multiplier,
            decimal_places=decimal_places,
            rarity_exponent=rarity_exponent,
            pair_scale_multiplier=pair_scale_multiplier,
            triple_scale_multiplier=triple_scale_multiplier,
        )
    )

    return SlotMachineConfig(
        starting_balance=max(
            ZERO,
            quantize_decimal(
                to_decimal(raw.get("starting_balance"), Decimal("100")),
                decimal_places,
            ),
        ),
        expected_multiplier_target=target_expected_multiplier,
        decimal_places=decimal_places,
        rarity_exponent=rarity_exponent,
        pair_scale_multiplier=pair_scale_multiplier,
        triple_scale_multiplier=triple_scale_multiplier,
        slot_faces=slot_faces,
        slot_double_multipliers=slot_double_multipliers,
        slot_triple_multipliers=slot_triple_multipliers,
        slot_probability_summary=probability_summary,
        history_limit=DEFAULT_HISTORY_LIMIT,
        milestone_thresholds=DEFAULT_MILESTONE_THRESHOLDS,
    )


def load_config() -> SlotMachineConfig:
    from .runtime import addon_config

    return config_from_raw(addon_config())
