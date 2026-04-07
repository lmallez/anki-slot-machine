from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from functools import lru_cache

from .config import SlotMachineConfig
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
    line_hit: bool
    slot_multiplier: Decimal
    matched_symbol: str | None
    animation_enabled: bool
    headline: str

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
            "line_hit": self.line_hit,
            "slot_multiplier": format_decimal(self.slot_multiplier, decimal_places),
            "matched_symbol": self.matched_symbol,
            "animation_enabled": self.animation_enabled,
            "headline": self.headline,
        }


@lru_cache(maxsize=32)
def _sorted_symbols(symbol_keys: tuple[str, ...]) -> tuple[str, ...]:
    def sort_key(symbol: str) -> tuple[int, str]:
        suffix = symbol.rsplit("_", 1)[-1]
        if suffix.isdigit():
            return int(suffix), symbol
        return 10_000, symbol

    return tuple(sorted(symbol_keys, key=sort_key))


def slot_symbols(config: SlotMachineConfig) -> tuple[str, ...]:
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


def neutral_reels(config: SlotMachineConfig) -> tuple[str, str, str]:
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


def weighted_symbol(config: SlotMachineConfig, *, rng: random.Random) -> str:
    strip = build_reel_strip(config)
    return spin_reel(strip, rng=rng)


def build_reel_strip(config: SlotMachineConfig) -> tuple[str, ...]:
    strip: list[str] = []
    for symbol in slot_symbols(config):
        strip.extend([symbol] * max(0, config.slot_faces.get(symbol, 0)))
    return tuple(strip) or (slot_symbols(config)[0],)


def shuffled_reel_strip(
    config: SlotMachineConfig, *, rng: random.Random
) -> tuple[str, ...]:
    strip = list(build_reel_strip(config))
    rng.shuffle(strip)
    return tuple(strip)


def spin_reel(strip: tuple[str, ...], *, rng: random.Random) -> str:
    if not strip:
        return "SLOT_1"
    return strip[rng.randrange(len(strip))]


def spin_reels(
    config: SlotMachineConfig, *, rng: random.Random
) -> tuple[str, str, str]:
    return tuple(
        spin_reel(shuffled_reel_strip(config, rng=rng), rng=rng) for _ in range(3)
    )


def slot_triple_multiplier_for_symbol(
    config: SlotMachineConfig, symbol: str
) -> Decimal:
    return quantize_decimal(
        config.slot_triple_multipliers.get(symbol, ONE),
        config.decimal_places,
    )


def slot_double_multiplier_for_symbol(
    config: SlotMachineConfig, symbol: str
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
    config: SlotMachineConfig, reels: tuple[str, str, str]
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
    config: SlotMachineConfig, reels: tuple[str, str, str]
) -> Decimal:
    multiplier, _, _ = evaluate_reels(config, reels)
    return multiplier


def _headline_symbol(symbol: str | None) -> str:
    if not symbol:
        return "slot"
    return symbol.replace("_", " ").title()


def build_spin_result(
    config: SlotMachineConfig,
    *,
    card_id: int,
    answer_key: str,
    bet: Decimal,
    balance_before: Decimal,
    rng: random.Random,
) -> SpinResult:
    did_spin = answer_key in {"good", "easy"}
    reels = ("MISS", "MISS", "MISS")
    slot_multiplier = ZERO
    payout = Decimal("0")
    line_hit = False
    base_reward = Decimal("0")
    slot_bonus = Decimal("0")
    matched_symbol = None
    match_count = 0

    if answer_key == "again":
        net_change = quantize_decimal(-bet, config.decimal_places)
        headline = f"{ANSWER_LABELS[answer_key]} loses ${format_decimal(bet, config.decimal_places)}"
        is_win = False
    else:
        if answer_key == "hard":
            base_reward = Decimal("0")
        else:
            base_reward = Decimal("2") if answer_key == "easy" else Decimal("1")
        base_reward = quantize_decimal(base_reward, config.decimal_places)
        if did_spin:
            reels = spin_reels(config, rng=rng)
            slot_multiplier, matched_symbol, match_count = evaluate_reels(config, reels)
            line_hit = match_count == 3
        else:
            reels = neutral_reels(config)
            slot_multiplier = ONE

        payout = quantize_decimal(
            base_reward * slot_multiplier,
            config.decimal_places,
        )
        slot_bonus = quantize_decimal(
            payout - base_reward,
            config.decimal_places,
        )
        net_change = payout
        if did_spin and matched_symbol and match_count == 3:
            headline = (
                f"{ANSWER_LABELS[answer_key]} hits {_headline_symbol(matched_symbol)} "
                f"x{format_decimal(slot_multiplier, config.decimal_places)} "
                f"for ${format_decimal(payout, config.decimal_places)}"
            )
        elif did_spin and matched_symbol and match_count == 2:
            headline = (
                f"{ANSWER_LABELS[answer_key]} lands a pair of {_headline_symbol(matched_symbol)} "
                f"for ${format_decimal(payout, config.decimal_places)}"
            )
        elif answer_key == "hard":
            headline = f"{ANSWER_LABELS[answer_key]} keeps the balance"
        else:
            headline = (
                f"{ANSWER_LABELS[answer_key]} earns "
                f"${format_decimal(payout, config.decimal_places)}"
            )
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
        line_hit=line_hit,
        slot_multiplier=slot_multiplier,
        matched_symbol=matched_symbol,
        animation_enabled=did_spin,
        headline=headline,
    )
