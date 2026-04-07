from __future__ import annotations

import random
from datetime import datetime
from decimal import Decimal

from .config import SlotMachineConfig, load_config
from .decimal_utils import format_decimal, quantize_decimal
from .game import SpinResult, answer_key_for_rating, build_spin_result
from .state import SlotMachineState, StateRepository

MILESTONE_NAMES = (
    "Starter Stack",
    "Bronze Reels",
    "Silver Reels",
    "Gold Reels",
    "Diamond Reels",
    "High Roller",
)
REVIEW_BET = Decimal("1")


class SlotMachineService:
    def __init__(self) -> None:
        self._repository = StateRepository()
        self._state: SlotMachineState | None = None
        self._rng = random.Random()

    def config(self) -> SlotMachineConfig:
        return load_config()

    def state(self) -> SlotMachineState:
        if self._state is None:
            self._state = self._repository.load(self.config())
        return self._state

    def snapshot(
        self, *, card_id: int | None = None, answer_button_count: int | None = None
    ) -> dict:
        config = self.config()
        state = self.state()

        next_unlock = next(
            (
                threshold
                for threshold in config.milestone_thresholds
                if state.balance < Decimal(threshold)
            ),
            None,
        )
        unlocked_count = sum(
            1
            for threshold in config.milestone_thresholds
            if state.balance >= Decimal(threshold)
        )
        tier_name = MILESTONE_NAMES[min(unlocked_count, len(MILESTONE_NAMES) - 1)]

        return {
            "balance": format_decimal(state.balance, config.decimal_places),
            "last_result": state.last_result,
            "card_id": card_id,
            "answer_button_count": answer_button_count,
            "tier_name": tier_name,
            "next_unlock_balance": (
                format_decimal(next_unlock, config.decimal_places)
                if next_unlock is not None
                else None
            ),
        }

    def apply_review(self, *, card_id: int, ease: int, button_count: int) -> SpinResult:
        config = self.config()
        state = self.state()
        previous_snapshot = state.review_snapshot(config.decimal_places)
        bet = quantize_decimal(REVIEW_BET, config.decimal_places)
        answer_key = answer_key_for_rating(ease, button_count)
        result = build_spin_result(
            config,
            card_id=card_id,
            answer_key=answer_key,
            bet=bet,
            balance_before=state.balance,
            rng=self._rng,
        )

        state.balance = result.balance_after
        if result.did_spin:
            state.spins += 1
        if result.is_win:
            state.total_won = quantize_decimal(
                state.total_won + result.payout,
                config.decimal_places,
            )
            state.current_streak += 1
            state.best_streak = max(state.best_streak, state.current_streak)
            state.biggest_jackpot = max(state.biggest_jackpot, result.payout)
        elif result.answer_key == "again":
            state.total_lost = quantize_decimal(
                state.total_lost + bet,
                config.decimal_places,
            )
            state.current_streak = 0
        else:
            state.current_streak = 0

        today = datetime.now().astimezone().date().isoformat()
        state.daily_earnings[today] = quantize_decimal(
            state.daily_earnings.get(today, Decimal("0")) + result.net_change,
            config.decimal_places,
        )
        serialized_result = result.to_dict(config.decimal_places)
        state.last_result = serialized_result
        state.history = [serialized_result, *state.history][: config.history_limit]
        state.undo_history = [previous_snapshot, *state.undo_history][: config.history_limit]
        self._repository.save(state, config)
        return result

    def undo_last_review(self) -> bool:
        config = self.config()
        state = self.state()
        if not state.undo_history:
            return False

        previous_snapshot = state.undo_history.pop(0)
        state.restore_review_snapshot(previous_snapshot, config)
        self._repository.save(state, config)
        return True

    def reset_progress(self) -> None:
        config = self.config()
        self._state = SlotMachineState.initial(config)
        self._repository.save(self._state, config)

    def stats_snapshot(self) -> dict:
        config = self.config()
        state = self.state()
        ordered_days = sorted(state.daily_earnings.items(), reverse=True)
        return {
            "balance": format_decimal(state.balance, config.decimal_places),
            "review_stake": format_decimal(REVIEW_BET, config.decimal_places),
            "total_won": format_decimal(state.total_won, config.decimal_places),
            "total_lost": format_decimal(state.total_lost, config.decimal_places),
            "spins": state.spins,
            "current_streak": state.current_streak,
            "best_streak": state.best_streak,
            "biggest_jackpot": format_decimal(
                state.biggest_jackpot,
                config.decimal_places,
            ),
            "history": state.history[:10],
            "daily_earnings": [
                (day, format_decimal(value, config.decimal_places))
                for day, value in ordered_days[:10]
            ],
        }


_service: SlotMachineService | None = None


def get_service() -> SlotMachineService:
    global _service

    if _service is None:
        _service = SlotMachineService()

    return _service
