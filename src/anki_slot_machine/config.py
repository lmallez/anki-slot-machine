from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from .decimal_utils import (
    ONE,
    THREE,
    ZERO,
    decimal_places_value,
    quantize_decimal,
    to_decimal,
)

DEFAULT_SLOT_PROFILE = {
    "name": "base",
    "faces": {
        "SLOT_1": 35,
        "SLOT_2": 25,
        "SLOT_3": 20,
        "SLOT_4": 12,
        "SLOT_5": 8,
    },
    "pair_multipliers": {
        "SLOT_1": 0.75,
        "SLOT_2": 0.95,
        "SLOT_3": 1.15,
        "SLOT_4": 2.20,
        "SLOT_5": 4.50,
    },
    "triple_multipliers": {
        "SLOT_1": 2.50,
        "SLOT_2": 7.00,
        "SLOT_3": 15.00,
        "SLOT_4": 60.00,
        "SLOT_5": 300.00,
    },
}
DEFAULT_SLOT_PROFILE_PATH = "slot_profiles/base.json"
DEFAULT_HISTORY_LIMIT = 30
DEFAULT_MILESTONE_THRESHOLDS = (250, 500, 1000, 2500)
DEFAULT_DECIMAL_PLACES = 2


@dataclass(frozen=True)
class SlotSymbolOdds:
    symbol: str
    faces: int
    single_probability: Decimal
    double_probability: Decimal
    triple_probability: Decimal
    double_multiplier: Decimal
    triple_multiplier: Decimal


@dataclass(frozen=True)
class SlotProbabilitySummary:
    profile_name: str
    profile_path: str
    symbol_odds: tuple[SlotSymbolOdds, ...]
    total_double_probability: Decimal
    total_triple_probability: Decimal
    no_match_probability: Decimal
    hit_probability: Decimal
    expected_multiplier: Decimal
    expected_good_payout: Decimal
    expected_easy_payout: Decimal


@dataclass(frozen=True)
class SlotMachineConfig:
    starting_balance: Decimal
    decimal_places: int
    slot_profile_path: str
    slot_profile_name: str
    slot_faces: dict[str, int]
    slot_double_multipliers: dict[str, Decimal]
    slot_triple_multipliers: dict[str, Decimal]
    slot_probability_summary: SlotProbabilitySummary
    history_limit: int
    milestone_thresholds: tuple[int, ...]


def _package_root(base_dir: Path | None = None) -> Path:
    return Path(base_dir) if base_dir is not None else Path(__file__).resolve().parent


def _sort_key(symbol: str) -> tuple[int, str]:
    suffix = symbol.rsplit("_", 1)[-1]
    if suffix.isdigit():
        return int(suffix), symbol
    return 10_000, symbol


def _sorted_slot_symbols(source: dict[str, object]) -> tuple[str, ...]:
    return tuple(sorted(source.keys(), key=_sort_key)) or ("SLOT_1",)


def _load_slot_profile_path(raw_value) -> str:
    if raw_value is None:
        return DEFAULT_SLOT_PROFILE_PATH
    value = str(raw_value).strip()
    return value or DEFAULT_SLOT_PROFILE_PATH


def _resolve_profile_path(profile_path: str, *, base_dir: Path | None = None) -> Path:
    candidate = Path(profile_path)
    if candidate.is_absolute():
        return candidate
    return _package_root(base_dir) / candidate


def _read_json_file(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _load_profile_payload(
    profile_path: str,
    *,
    base_dir: Path | None = None,
) -> tuple[str, str, dict]:
    resolved_path = _resolve_profile_path(profile_path, base_dir=base_dir)
    payload = _read_json_file(resolved_path)
    if payload is not None:
        profile_name = str(payload.get("name") or resolved_path.stem)
        return profile_name, str(resolved_path), payload

    fallback_path = _resolve_profile_path(DEFAULT_SLOT_PROFILE_PATH, base_dir=base_dir)
    fallback_payload = _read_json_file(fallback_path)
    if fallback_payload is not None:
        profile_name = str(fallback_payload.get("name") or fallback_path.stem)
        return profile_name, str(fallback_path), fallback_payload

    profile_name = str(DEFAULT_SLOT_PROFILE.get("name") or "default_slot_profile")
    return profile_name, str(fallback_path), dict(DEFAULT_SLOT_PROFILE)


def _load_slot_faces(raw: dict | None) -> dict[str, int]:
    source = raw if isinstance(raw, dict) else {}
    defaults = DEFAULT_SLOT_PROFILE["faces"]
    faces: dict[str, int] = {}
    for key in _sorted_slot_symbols(defaults):
        default_value = defaults.get(key, 0)
        try:
            faces[key] = max(0, int(source.get(key, default_value)))
        except (TypeError, ValueError):
            faces[key] = default_value
    if any(value > 0 for value in faces.values()):
        return faces
    return dict(defaults)


def _load_multiplier_table(
    raw: dict | None,
    *,
    defaults: dict[str, int | float],
    symbols: tuple[str, ...],
    decimal_places: int,
) -> dict[str, Decimal]:
    source = raw if isinstance(raw, dict) else {}
    table: dict[str, Decimal] = {}
    for symbol in symbols:
        fallback = to_decimal(defaults.get(symbol, ONE), ONE)
        table[symbol] = max(
            ZERO,
            quantize_decimal(to_decimal(source.get(symbol), fallback), decimal_places),
        )
    return table


def _build_probability_summary(
    *,
    profile_name: str,
    profile_path: str,
    slot_faces: dict[str, int],
    slot_double_multipliers: dict[str, Decimal],
    slot_triple_multipliers: dict[str, Decimal],
    decimal_places: int,
) -> SlotProbabilitySummary:
    symbols = _sorted_slot_symbols(slot_faces)
    total_faces = sum(max(0, slot_faces.get(symbol, 0)) for symbol in symbols)
    if total_faces <= 0:
        total_faces = sum(DEFAULT_SLOT_PROFILE["faces"].values())
        slot_faces = dict(DEFAULT_SLOT_PROFILE["faces"])
        symbols = _sorted_slot_symbols(slot_faces)

    total_faces_decimal = Decimal(total_faces)
    symbol_odds: list[SlotSymbolOdds] = []
    total_double_probability = ZERO
    total_triple_probability = ZERO
    expected_multiplier_raw = ZERO

    for symbol in symbols:
        probability = Decimal(slot_faces.get(symbol, 0)) / total_faces_decimal
        double_probability = THREE * (probability**2) * (ONE - probability)
        triple_probability = probability**3
        double_multiplier = quantize_decimal(
            slot_double_multipliers.get(symbol, ONE),
            decimal_places,
        )
        triple_multiplier = quantize_decimal(
            slot_triple_multipliers.get(symbol, ONE),
            decimal_places,
        )
        symbol_odds.append(
            SlotSymbolOdds(
                symbol=symbol,
                faces=slot_faces.get(symbol, 0),
                single_probability=probability,
                double_probability=double_probability,
                triple_probability=triple_probability,
                double_multiplier=double_multiplier,
                triple_multiplier=triple_multiplier,
            )
        )
        total_double_probability += double_probability
        total_triple_probability += triple_probability
        expected_multiplier_raw += double_probability * double_multiplier
        expected_multiplier_raw += triple_probability * triple_multiplier

    no_match_probability = max(
        ZERO,
        ONE - total_double_probability - total_triple_probability,
    )
    hit_probability = max(
        ZERO,
        total_double_probability + total_triple_probability,
    )
    expected_multiplier = quantize_decimal(expected_multiplier_raw, decimal_places)
    return SlotProbabilitySummary(
        profile_name=profile_name,
        profile_path=profile_path,
        symbol_odds=tuple(symbol_odds),
        total_double_probability=total_double_probability,
        total_triple_probability=total_triple_probability,
        no_match_probability=no_match_probability,
        hit_probability=hit_probability,
        expected_multiplier=expected_multiplier,
        expected_good_payout=expected_multiplier,
        expected_easy_payout=quantize_decimal(
            expected_multiplier_raw * Decimal("2"),
            decimal_places,
        ),
    )


def config_from_raw(
    raw: dict | None,
    *,
    base_dir: Path | None = None,
) -> SlotMachineConfig:
    raw = raw or {}
    decimal_places = decimal_places_value(
        raw.get("decimal_places"),
        DEFAULT_DECIMAL_PLACES,
    )
    profile_path = _load_slot_profile_path(raw.get("slot_profile_path"))
    profile_name, resolved_profile_path, profile_payload = _load_profile_payload(
        profile_path,
        base_dir=base_dir,
    )
    slot_faces = _load_slot_faces(profile_payload.get("faces"))
    symbols = _sorted_slot_symbols(slot_faces)
    slot_double_multipliers = _load_multiplier_table(
        profile_payload.get("pair_multipliers"),
        defaults=DEFAULT_SLOT_PROFILE["pair_multipliers"],
        symbols=symbols,
        decimal_places=decimal_places,
    )
    slot_triple_multipliers = _load_multiplier_table(
        profile_payload.get("triple_multipliers"),
        defaults=DEFAULT_SLOT_PROFILE["triple_multipliers"],
        symbols=symbols,
        decimal_places=decimal_places,
    )
    probability_summary = _build_probability_summary(
        profile_name=profile_name,
        profile_path=resolved_profile_path,
        slot_faces=slot_faces,
        slot_double_multipliers=slot_double_multipliers,
        slot_triple_multipliers=slot_triple_multipliers,
        decimal_places=decimal_places,
    )

    return SlotMachineConfig(
        starting_balance=max(
            ZERO,
            quantize_decimal(
                to_decimal(raw.get("starting_balance"), Decimal("100")),
                decimal_places,
            ),
        ),
        decimal_places=decimal_places,
        slot_profile_path=profile_path,
        slot_profile_name=profile_name,
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
