from __future__ import annotations

import hashlib
import random
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from functools import lru_cache

from .config import SlotMachineConfig, SlotMachineDefinition
from .decimal_utils import ONE, ZERO, format_decimal, quantize_decimal

ANSWER_LABELS = {
    "again": "Again",
    "hard": "Hard",
    "good": "Good",
    "easy": "Easy",
}


@dataclass(frozen=True)
class SpinResult:
    event_id: str
    timestamp: str
    card_id: int
    answer_key: str
    answer_label: str
    bet: Decimal
    payout: Decimal
    base_reward: Decimal
    slot_bonus: Decimal
    net_change: Decimal
    balance_after: Decimal
    reels: tuple[str, str, str]
    is_win: bool
    did_spin: bool
    no_spin: bool
    line_hit: bool
    slot_multiplier: Decimal
    matched_symbol: str | None
    reel_start_positions: tuple[int, int, int]
    reel_positions: tuple[int, int, int]
    reel_step_counts: tuple[int, int, int]
    animation_enabled: bool
    headline: str
    machine_key: str = ""
    machine_label: str = ""

    def to_dict(self, decimal_places: int) -> dict:
        payload = {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "card_id": self.card_id,
            "answer_key": self.answer_key,
            "answer_label": self.answer_label,
            "bet": format_decimal(self.bet, decimal_places),
            "payout": format_decimal(self.payout, decimal_places),
            "base_reward": format_decimal(self.base_reward, decimal_places),
            "slot_bonus": format_decimal(self.slot_bonus, decimal_places),
            "net_change": format_decimal(self.net_change, decimal_places),
            "balance_after": format_decimal(self.balance_after, decimal_places),
            "reels": list(self.reels),
            "is_win": self.is_win,
            "did_spin": self.did_spin,
            "no_spin": self.no_spin,
            "line_hit": self.line_hit,
            "slot_multiplier": format_decimal(self.slot_multiplier, decimal_places),
            "matched_symbol": self.matched_symbol,
            "reel_start_positions": list(self.reel_start_positions),
            "reel_positions": list(self.reel_positions),
            "reel_step_counts": list(self.reel_step_counts),
            "animation_enabled": self.animation_enabled,
            "headline": self.headline,
        }
        if self.machine_key:
            payload["machine_key"] = self.machine_key
        if self.machine_label:
            payload["machine_label"] = self.machine_label
        return payload


@dataclass(frozen=True)
class RoundSpinResult:
    event_id: str
    timestamp: str
    card_id: int
    answer_key: str
    answer_label: str
    bet: Decimal
    payout: Decimal
    base_reward: Decimal
    slot_bonus: Decimal
    net_change: Decimal
    balance_after: Decimal
    reels: tuple[str, str, str]
    is_win: bool
    did_spin: bool
    no_spin: bool
    line_hit: bool
    slot_multiplier: Decimal
    matched_symbol: str | None
    reel_start_positions: tuple[int, int, int]
    reel_positions: tuple[int, int, int]
    reel_step_counts: tuple[int, int, int]
    animation_enabled: bool
    headline: str
    machine_results: tuple[dict[str, object], ...]

    def to_dict(self, decimal_places: int) -> dict:
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "card_id": self.card_id,
            "answer_key": self.answer_key,
            "answer_label": self.answer_label,
            "bet": format_decimal(self.bet, decimal_places),
            "payout": format_decimal(self.payout, decimal_places),
            "base_reward": format_decimal(self.base_reward, decimal_places),
            "slot_bonus": format_decimal(self.slot_bonus, decimal_places),
            "net_change": format_decimal(self.net_change, decimal_places),
            "balance_after": format_decimal(self.balance_after, decimal_places),
            "reels": list(self.reels),
            "is_win": self.is_win,
            "did_spin": self.did_spin,
            "no_spin": self.no_spin,
            "line_hit": self.line_hit,
            "slot_multiplier": format_decimal(self.slot_multiplier, decimal_places),
            "matched_symbol": self.matched_symbol,
            "reel_start_positions": list(self.reel_start_positions),
            "reel_positions": list(self.reel_positions),
            "reel_step_counts": list(self.reel_step_counts),
            "animation_enabled": self.animation_enabled,
            "headline": self.headline,
            "machine_results": list(self.machine_results),
        }


@lru_cache(maxsize=32)
def _sorted_symbols(symbol_keys: tuple[str, ...]) -> tuple[str, ...]:
    def sort_key(symbol: str) -> tuple[int, str]:
        suffix = symbol.rsplit("_", 1)[-1]
        if suffix.isdigit():
            return int(suffix), symbol
        return 10_000, symbol

    return tuple(sorted(symbol_keys, key=sort_key))


def slot_symbols(config: SlotMachineConfig | SlotMachineDefinition) -> tuple[str, ...]:
    keys = tuple(
        dict.fromkeys(
            [
                *config.slot_faces.keys(),
                *config.slot_double_multipliers.keys(),
                *config.slot_triple_multipliers.keys(),
            ]
        )
    )
    symbols = _sorted_symbols(keys)
    return symbols or ("SLOT_1",)


def neutral_reels(
    config: SlotMachineConfig | SlotMachineDefinition,
) -> tuple[str, str, str]:
    symbols = slot_symbols(config)
    if len(symbols) == 1:
        return (symbols[0], symbols[0], symbols[0])
    if len(symbols) == 2:
        return (symbols[0], symbols[1], symbols[0])
    return symbols[:3]


def answer_key_for_rating(ease: int, button_count: int) -> str:
    if button_count <= 2:
        return {1: "again", 2: "good"}.get(ease, "good")
    if button_count == 3:
        return {1: "again", 2: "good", 3: "easy"}.get(ease, "good")
    return {1: "again", 2: "hard", 3: "good", 4: "easy"}.get(ease, "good")


def weighted_symbol(
    config: SlotMachineConfig | SlotMachineDefinition, *, rng: random.Random
) -> str:
    strip = build_reel_strip(config)
    return spin_reel(strip, rng=rng)


def build_reel_strip(
    config: SlotMachineConfig | SlotMachineDefinition,
) -> tuple[str, ...]:
    symbols = tuple(
        symbol
        for symbol in slot_symbols(config)
        if max(0, config.slot_faces.get(symbol, 0)) > 0
    )
    if not symbols:
        return (slot_symbols(config)[0],)

    remaining = {symbol: max(0, config.slot_faces.get(symbol, 0)) for symbol in symbols}
    seed = "|".join(
        [
            str(getattr(config, "slot_profile_name", "") or ""),
            str(getattr(config, "slot_profile_path", "") or ""),
            str(getattr(config, "key", "") or ""),
        ]
    )
    symbol_order = {
        symbol: int.from_bytes(
            hashlib.sha256(f"{seed}:{symbol}".encode("utf-8")).digest()[:8],
            "big",
        )
        for symbol in symbols
    }

    strip: list[str] = []
    previous_symbol: str | None = None
    total_faces = sum(remaining.values())
    for _ in range(total_faces):
        candidates = [
            symbol
            for symbol in symbols
            if remaining[symbol] > 0 and symbol != previous_symbol
        ]
        if not candidates:
            candidates = [symbol for symbol in symbols if remaining[symbol] > 0]
        chosen = min(
            candidates, key=lambda symbol: (-remaining[symbol], symbol_order[symbol])
        )
        strip.append(chosen)
        remaining[chosen] -= 1
        previous_symbol = chosen

    if len(strip) > 1 and strip[0] == strip[-1]:
        for index in range(len(strip) - 2, 0, -1):
            candidate = strip[index]
            before = strip[index - 1]
            if candidate == strip[0] or before == strip[0]:
                continue
            strip[index], strip[-1] = strip[-1], strip[index]
            break

    return tuple(strip)


def shuffled_reel_strip(
    config: SlotMachineConfig | SlotMachineDefinition, *, rng: random.Random
) -> tuple[str, ...]:
    strip = list(build_reel_strip(config))
    rng.shuffle(strip)
    return tuple(strip)


def spin_reel(strip: tuple[str, ...], *, rng: random.Random) -> str:
    if not strip:
        return "SLOT_1"
    return strip[rng.randrange(len(strip))]


def spin_reel_position(strip: tuple[str, ...], *, rng: random.Random) -> int:
    if not strip:
        return 0
    return rng.randrange(len(strip))


def spin_reel_positions(
    config: SlotMachineConfig | SlotMachineDefinition, *, rng: random.Random
) -> tuple[int, int, int]:
    strip = build_reel_strip(config)
    return tuple(spin_reel_position(strip, rng=rng) for _ in range(3))


def spin_reels(
    config: SlotMachineConfig | SlotMachineDefinition, *, rng: random.Random
) -> tuple[str, str, str]:
    return visible_reels_for_positions(config, spin_reel_positions(config, rng=rng))


def reel_symbol_at_position(strip: tuple[str, ...], position: int) -> str:
    if not strip:
        return "SLOT_1"
    return strip[position % len(strip)]


def default_reel_positions(
    config: SlotMachineConfig | SlotMachineDefinition,
) -> tuple[int, int, int]:
    strip = build_reel_strip(config)
    neutral = neutral_reels(config)
    positions: list[int] = []
    for symbol in neutral:
        try:
            positions.append(strip.index(symbol))
        except ValueError:
            positions.append(0)
    return tuple(positions[:3])  # type: ignore[return-value]


def normalize_reel_positions(
    config: SlotMachineConfig | SlotMachineDefinition,
    positions: tuple[int, int, int] | list[int] | None,
) -> tuple[int, int, int]:
    strip = build_reel_strip(config)
    strip_length = max(1, len(strip))
    if not isinstance(positions, (tuple, list)) or len(positions) != 3:
        return default_reel_positions(config)
    normalized: list[int] = []
    for value in positions[:3]:
        try:
            normalized.append(int(value) % strip_length)
        except (TypeError, ValueError):
            normalized.append(0)
    return tuple(normalized)  # type: ignore[return-value]


def visible_reels_for_positions(
    config: SlotMachineConfig | SlotMachineDefinition,
    positions: tuple[int, int, int] | list[int] | None,
) -> tuple[str, str, str]:
    strip = build_reel_strip(config)
    normalized = normalize_reel_positions(config, positions)
    return tuple(reel_symbol_at_position(strip, position) for position in normalized)  # type: ignore[return-value]


def advance_reel_to_symbol(
    strip: tuple[str, ...],
    *,
    start_position: int,
    target_symbol: str,
    min_steps: int,
    rng: random.Random,
) -> tuple[int, int]:
    if not strip:
        return 0, max(0, int(min_steps))

    normalized_start = start_position % len(strip)
    matching_positions = [
        index for index, symbol in enumerate(strip) if symbol == target_symbol
    ]
    if not matching_positions:
        matching_positions = [normalized_start]

    landing_position = matching_positions[rng.randrange(len(matching_positions))]
    step_count = (landing_position - normalized_start) % len(strip)
    if step_count == 0:
        step_count = len(strip)
    minimum = max(1, int(min_steps))
    if step_count < minimum:
        extra_turns = (minimum - step_count + len(strip) - 1) // len(strip)
        step_count += extra_turns * len(strip)

    return (normalized_start + step_count) % len(strip), step_count


def advance_reel_to_position(
    strip: tuple[str, ...],
    *,
    start_position: int,
    target_position: int,
    min_steps: int,
) -> tuple[int, int]:
    if not strip:
        return 0, max(0, int(min_steps))

    strip_length = len(strip)
    normalized_start = start_position % strip_length
    normalized_target = target_position % strip_length
    step_count = (normalized_target - normalized_start) % strip_length
    if step_count == 0:
        step_count = strip_length
    minimum = max(1, int(min_steps))
    if step_count < minimum:
        extra_turns = (minimum - step_count + strip_length - 1) // strip_length
        step_count += extra_turns * strip_length

    return normalized_target, step_count


def slot_triple_multiplier_for_symbol(
    config: SlotMachineConfig | SlotMachineDefinition, symbol: str
) -> Decimal:
    return quantize_decimal(
        config.slot_triple_multipliers.get(symbol, ONE),
        config.decimal_places,
    )


def slot_double_multiplier_for_symbol(
    config: SlotMachineConfig | SlotMachineDefinition, symbol: str
) -> Decimal:
    return quantize_decimal(
        config.slot_double_multipliers.get(symbol, ONE),
        config.decimal_places,
    )


def matched_symbol_for_reels(reels: tuple[str, str, str]) -> str | None:
    return reels[0] if len(set(reels)) == 1 else None


def pair_symbol_for_reels(reels: tuple[str, str, str]) -> str | None:
    counts = Counter(reels)
    for symbol, count in counts.items():
        if count == 2:
            return symbol
    return None


def evaluate_reels(
    config: SlotMachineConfig | SlotMachineDefinition, reels: tuple[str, str, str]
) -> tuple[Decimal, str | None, int]:
    matched_symbol = matched_symbol_for_reels(reels)
    if matched_symbol:
        return (
            slot_triple_multiplier_for_symbol(config, matched_symbol),
            matched_symbol,
            3,
        )

    pair_symbol = pair_symbol_for_reels(reels)
    if pair_symbol:
        return slot_double_multiplier_for_symbol(config, pair_symbol), pair_symbol, 2

    return ZERO, None, 1


def slot_multiplier_for_reels(
    config: SlotMachineConfig | SlotMachineDefinition, reels: tuple[str, str, str]
) -> Decimal:
    multiplier, _, _ = evaluate_reels(config, reels)
    return multiplier


def _headline_symbol(symbol: str | None) -> str:
    if not symbol:
        return "slot"
    return symbol.replace("_", " ").title()


def _signed_amount(amount: Decimal, decimal_places: int) -> str:
    value = format_decimal(abs(amount), decimal_places)
    if amount > ZERO:
        return f"+${value}"
    if amount < ZERO:
        return f"-${value}"
    return f"${value}"


def _clamp_negative_change(change: Decimal, *, balance_before: Decimal) -> Decimal:
    if change >= ZERO:
        return change
    return max(-balance_before, change)


def _configured_base_value(
    config: SlotMachineConfig | SlotMachineDefinition,
    *,
    answer_key: str,
    bet: Decimal,
) -> Decimal:
    if answer_key == "again":
        fallback = ZERO
    elif answer_key == "hard":
        fallback = Decimal("0.5")
    elif answer_key == "easy":
        fallback = Decimal("1.5")
    else:
        fallback = Decimal("1")
    return quantize_decimal(
        config.answer_base_values.get(answer_key, fallback),
        config.decimal_places,
    )


def build_spin_result(
    config: SlotMachineConfig | SlotMachineDefinition,
    *,
    card_id: int,
    answer_key: str,
    bet: Decimal,
    balance_before: Decimal,
    rng: random.Random,
    previous_reel_positions: tuple[int, int, int] | list[int] | None = None,
    did_spin_override: bool | None = None,
) -> SpinResult:
    configured_base_reward = _configured_base_value(
        config,
        answer_key=answer_key,
        bet=bet,
    )
    did_spin = (
        bool(did_spin_override)
        if did_spin_override is not None
        else configured_base_reward != ZERO
    )
    if configured_base_reward == ZERO:
        did_spin = False
    no_spin = not did_spin
    strip = build_reel_strip(config)
    reel_start_positions = normalize_reel_positions(config, previous_reel_positions)
    reel_positions = reel_start_positions
    reel_step_counts = (0, 0, 0)
    reels = visible_reels_for_positions(config, reel_positions)
    slot_multiplier = ZERO
    payout = ZERO
    line_hit = False
    base_reward = configured_base_reward
    slot_bonus = ZERO
    matched_symbol = None
    match_count = 0
    if did_spin:
        reel_positions = spin_reel_positions(config, rng=rng)
        reels = visible_reels_for_positions(config, reel_positions)
        end_positions: list[int] = []
        step_counts: list[int] = []
        for reel_index, target_position in enumerate(reel_positions):
            end_position, step_count = advance_reel_to_position(
                strip,
                start_position=reel_start_positions[reel_index],
                target_position=target_position,
                min_steps=(len(strip) * 2) + 9 + (reel_index * max(4, len(strip) // 3)),
            )
            end_positions.append(end_position)
            step_counts.append(step_count)
        reel_positions = tuple(end_positions)  # type: ignore[assignment]
        reel_step_counts = tuple(step_counts)  # type: ignore[assignment]
        slot_multiplier, matched_symbol, match_count = evaluate_reels(config, reels)
        line_hit = match_count == 3
        raw_change = quantize_decimal(
            base_reward * slot_multiplier,
            config.decimal_places,
        )
    else:
        raw_change = ZERO

    payout = quantize_decimal(
        _clamp_negative_change(raw_change, balance_before=balance_before),
        config.decimal_places,
    )
    slot_bonus = (
        quantize_decimal(
            payout - base_reward,
            config.decimal_places,
        )
        if did_spin
        else ZERO
    )
    net_change = payout
    if did_spin and matched_symbol and match_count == 3:
        headline = (
            f"{ANSWER_LABELS[answer_key]} hits {_headline_symbol(matched_symbol)} "
            f"x{format_decimal(slot_multiplier, config.decimal_places)} "
            f"for {_signed_amount(net_change, config.decimal_places)}"
        )
    elif did_spin and matched_symbol and match_count == 2:
        headline = (
            f"{ANSWER_LABELS[answer_key]} lands a pair of {_headline_symbol(matched_symbol)} "
            f"for {_signed_amount(net_change, config.decimal_places)}"
        )
    elif net_change > ZERO:
        headline = (
            f"{ANSWER_LABELS[answer_key]} earns "
            f"{_signed_amount(net_change, config.decimal_places)}"
        )
    elif net_change < ZERO:
        headline = (
            f"{ANSWER_LABELS[answer_key]} loses "
            f"${format_decimal(abs(net_change), config.decimal_places)}"
        )
    else:
        headline = f"{ANSWER_LABELS[answer_key]} keeps the balance"
    is_win = payout > ZERO

    balance_after = quantize_decimal(
        balance_before + net_change,
        config.decimal_places,
    )
    now = datetime.now().astimezone()
    event_id = f"{int(now.timestamp() * 1000)}-{card_id}"

    return SpinResult(
        event_id=event_id,
        timestamp=now.isoformat(),
        card_id=card_id,
        answer_key=answer_key,
        answer_label=ANSWER_LABELS[answer_key],
        bet=bet,
        payout=payout,
        base_reward=base_reward,
        slot_bonus=slot_bonus,
        net_change=net_change,
        balance_after=balance_after,
        reels=reels,
        is_win=is_win,
        did_spin=did_spin,
        no_spin=no_spin,
        line_hit=line_hit,
        slot_multiplier=slot_multiplier,
        matched_symbol=matched_symbol,
        reel_start_positions=reel_start_positions,
        reel_positions=reel_positions,
        reel_step_counts=reel_step_counts,
        animation_enabled=did_spin,
        headline=headline,
        machine_key=str(getattr(config, "key", "") or ""),
        machine_label=str(getattr(config, "label", "") or ""),
    )


def build_round_result(
    config: SlotMachineConfig,
    *,
    card_id: int,
    answer_key: str,
    bet: Decimal,
    balance_before: Decimal,
    rng: random.Random,
    previous_reel_positions_by_machine: (
        dict[str, tuple[int, int, int] | list[int]] | None
    ) = None,
    did_spin_override: bool | None = None,
) -> RoundSpinResult:
    running_balance = quantize_decimal(balance_before, config.decimal_places)
    machine_spin_results: list[SpinResult] = []
    now = datetime.now().astimezone()

    if not config.machines:
        return RoundSpinResult(
            event_id=f"{int(now.timestamp() * 1000)}-{card_id}",
            timestamp=now.isoformat(),
            card_id=card_id,
            answer_key=answer_key,
            answer_label=ANSWER_LABELS[answer_key],
            bet=bet,
            payout=ZERO,
            base_reward=ZERO,
            slot_bonus=ZERO,
            net_change=ZERO,
            balance_after=running_balance,
            reels=("MISS", "MISS", "MISS"),
            is_win=False,
            did_spin=False,
            no_spin=True,
            line_hit=False,
            slot_multiplier=ZERO,
            matched_symbol=None,
            reel_start_positions=(0, 0, 0),
            reel_positions=(0, 0, 0),
            reel_step_counts=(0, 0, 0),
            animation_enabled=False,
            headline=f"{ANSWER_LABELS[answer_key]} keeps the balance",
            machine_results=(),
        )

    for machine in config.machines:
        machine_result = build_spin_result(
            machine,
            card_id=card_id,
            answer_key=answer_key,
            bet=bet,
            balance_before=running_balance,
            rng=rng,
            previous_reel_positions=(previous_reel_positions_by_machine or {}).get(
                machine.key
            ),
            did_spin_override=did_spin_override,
        )
        machine_spin_results.append(machine_result)
        running_balance = machine_result.balance_after

    payout = quantize_decimal(
        sum((result.payout for result in machine_spin_results), ZERO),
        config.decimal_places,
    )
    base_reward = quantize_decimal(
        sum((result.base_reward for result in machine_spin_results), ZERO),
        config.decimal_places,
    )
    slot_bonus = quantize_decimal(
        sum((result.slot_bonus for result in machine_spin_results), ZERO),
        config.decimal_places,
    )
    net_change = quantize_decimal(
        sum((result.net_change for result in machine_spin_results), ZERO),
        config.decimal_places,
    )
    machine_count = len(machine_spin_results)
    first_result = machine_spin_results[0]
    event_id = first_result.event_id
    timestamp = first_result.timestamp
    machine_results = tuple(
        {
            **result.to_dict(config.decimal_places),
            "event_id": event_id,
            "timestamp": timestamp,
        }
        for result in machine_spin_results
    )

    if machine_count == 1:
        reels = first_result.reels
        line_hit = first_result.line_hit
        slot_multiplier = first_result.slot_multiplier
        matched_symbol = first_result.matched_symbol
        reel_start_positions = first_result.reel_start_positions
        reel_positions = first_result.reel_positions
        reel_step_counts = first_result.reel_step_counts
        headline = first_result.headline
    else:
        reels = ("MISS", "MISS", "MISS")
        line_hit = False
        slot_multiplier = ZERO
        matched_symbol = None
        reel_start_positions = (0, 0, 0)
        reel_positions = (0, 0, 0)
        reel_step_counts = (0, 0, 0)
        direction = (
            "earns" if net_change > ZERO else "loses" if net_change < ZERO else "keeps"
        )
        if net_change > ZERO:
            headline = (
                f"{ANSWER_LABELS[answer_key]} settles {machine_count} machines for "
                f"${format_decimal(payout, config.decimal_places)}"
            )
        elif net_change < ZERO:
            headline = (
                f"{ANSWER_LABELS[answer_key]} loses "
                f"${format_decimal(abs(net_change), config.decimal_places)} across "
                f"{machine_count} machines"
            )
        else:
            headline = (
                f"{ANSWER_LABELS[answer_key]} {direction} the balance across "
                f"{machine_count} machines"
            )

    did_spin = any(result.did_spin for result in machine_spin_results)
    no_spin = all(result.no_spin for result in machine_spin_results)

    return RoundSpinResult(
        event_id=event_id,
        timestamp=timestamp,
        card_id=card_id,
        answer_key=answer_key,
        answer_label=ANSWER_LABELS[answer_key],
        bet=bet,
        payout=payout,
        base_reward=base_reward,
        slot_bonus=slot_bonus,
        net_change=net_change,
        balance_after=running_balance,
        reels=reels,
        is_win=net_change > ZERO,
        did_spin=did_spin,
        no_spin=no_spin,
        line_hit=line_hit,
        slot_multiplier=slot_multiplier,
        matched_symbol=matched_symbol,
        reel_start_positions=reel_start_positions,
        reel_positions=reel_positions,
        reel_step_counts=reel_step_counts,
        animation_enabled=did_spin,
        headline=headline,
        machine_results=machine_results,
    )
