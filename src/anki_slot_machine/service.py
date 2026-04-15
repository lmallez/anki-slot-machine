from __future__ import annotations

import random
from datetime import datetime
from decimal import Decimal

from .config import SlotMachineConfig, load_config
from .decimal_utils import format_decimal, quantize_decimal
from .game import (
    RoundSpinResult,
    answer_key_for_rating,
    build_reel_strip,
    build_round_result,
    default_reel_positions,
)
from .runtime import addon_instance_key, addon_package_name
from .state import UNDO_HISTORY_LIMIT, SlotMachineState, StateRepository

MILESTONE_NAMES = (
    "Starter Stack",
    "Bronze Reels",
    "Silver Reels",
    "Gold Reels",
    "Diamond Reels",
    "High Roller",
)
REVIEW_BET = Decimal("1")
HISTORY_FORMAT_VERSION = 2
TREND_EPSILON = Decimal("0.01")


def _prepend_capped(items: list, entry, limit: int) -> None:
    items.insert(0, entry)
    if len(items) > limit:
        del items[limit:]


def _answer_base_value(config: SlotMachineConfig, answer_key: str) -> Decimal:
    if answer_key == "again":
        fallback = Decimal("0")
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


def _should_trigger_spin(
    *,
    stacked_value: Decimal,
    config: SlotMachineConfig,
    rng: random.Random,
) -> bool:
    if stacked_value == Decimal("0"):
        return False
    return rng.random() < float(config.spin_trigger_chance)


def _event_decimal(event: dict, field_name: str) -> Decimal:
    return Decimal(str(event.get(field_name, "0")))


def _recent_events(events: list[dict], window_size: int) -> list[dict]:
    if window_size <= 0:
        return []
    return events[-window_size:]


def _previous_recent_events(events: list[dict], window_size: int) -> list[dict]:
    if window_size <= 0:
        return []
    return events[-window_size * 2 : -window_size]


def _net_total(events: list[dict]) -> Decimal:
    total = Decimal("0")
    for event in events:
        total += _event_decimal(event, "net_change")
    return total


def _machine_results_for_event(event: dict) -> list[dict]:
    raw_results = event.get("machine_results")
    if isinstance(raw_results, list):
        return [item for item in raw_results if isinstance(item, dict)]
    return [event]


def _is_undoable_slot_event(
    *,
    result: RoundSpinResult,
    previous_reel_positions: dict[str, list[int]],
    next_reel_positions: dict[str, list[int]],
    previous_trigger_count: int,
    next_trigger_count: int,
) -> bool:
    if result.did_spin:
        return True
    if result.net_change != Decimal("0"):
        return True
    if previous_trigger_count != next_trigger_count:
        return True
    return previous_reel_positions != next_reel_positions


def _trend_payload(
    current_events: list[dict], previous_events: list[dict]
) -> dict[str, str]:
    current_total = _net_total(current_events)
    previous_total = _net_total(previous_events)
    current_count = max(1, len(current_events))
    previous_count = max(1, len(previous_events))
    current_rate = current_total / Decimal(current_count)
    previous_rate = previous_total / Decimal(previous_count)

    if not previous_events:
        if current_total > TREND_EPSILON:
            return {"direction": "up", "arrow": "↑", "label": "accelerating"}
        if current_total < -TREND_EPSILON:
            return {"direction": "down", "arrow": "↓", "label": "cooling off"}
        return {"direction": "flat", "arrow": "→", "label": "steady"}

    delta = current_rate - previous_rate
    if delta > TREND_EPSILON:
        return {"direction": "up", "arrow": "↑", "label": "accelerating"}
    if delta < -TREND_EPSILON:
        return {"direction": "down", "arrow": "↓", "label": "cooling off"}
    return {"direction": "flat", "arrow": "→", "label": "steady"}


def _streak_context(streak: int) -> str:
    if streak <= 0:
        return "cooled off"
    if streak == 1:
        return "just started"
    if streak <= 3:
        return "warming up"
    if streak <= 6:
        return "hot streak"
    return "on fire"


def _session_temperature(
    *, today_net: Decimal, recent_trend: str, current_streak: int
) -> str:
    if current_streak >= 4 and today_net >= Decimal("0"):
        return "heating up"
    if today_net > TREND_EPSILON and recent_trend == "up":
        return "heating up"
    if today_net < -TREND_EPSILON and recent_trend == "down":
        return "cooling down"
    return "holding steady"


def _volatility_label(
    *,
    average_win: Decimal,
    best_win: Decimal,
    worst_loss: Decimal,
) -> str:
    if best_win <= Decimal("0") and worst_loss <= Decimal("0"):
        return "quiet"
    if average_win > Decimal("0") and best_win >= average_win * Decimal("5"):
        return "spiky"
    if worst_loss >= best_win and worst_loss > Decimal("0"):
        return "swingy"
    if best_win > worst_loss * Decimal("2"):
        return "upside-biased"
    return "balanced"


def _recent_summary(
    events: list[dict], *, window_size: int, decimal_places: int
) -> dict:
    current_events = _recent_events(events, window_size)
    previous_events = _previous_recent_events(events, window_size)
    trend = _trend_payload(current_events, previous_events)

    spin_count = 0
    hit_count = 0
    win_total = Decimal("0")
    loss_total = Decimal("0")
    win_events = 0
    loss_events = 0

    for event in current_events:
        for machine_result in _machine_results_for_event(event):
            if machine_result.get("did_spin"):
                spin_count += 1
                if machine_result.get("matched_symbol"):
                    hit_count += 1

        net_change = _event_decimal(event, "net_change")
        if net_change > Decimal("0"):
            win_events += 1
            win_total += net_change
        elif net_change < Decimal("0"):
            loss_events += 1
            loss_total += abs(net_change)

    total_net = quantize_decimal(_net_total(current_events), decimal_places)
    hit_rate = round((hit_count / spin_count) * 100, 1) if spin_count else 0.0
    average_win = quantize_decimal(
        win_total / win_events if win_events else Decimal("0"),
        decimal_places,
    )
    average_loss = quantize_decimal(
        loss_total / loss_events if loss_events else Decimal("0"),
        decimal_places,
    )

    return {
        "label": f"Last {len(current_events)}",
        "review_count": len(current_events),
        "spin_count": spin_count,
        "hit_count": hit_count,
        "hit_rate": hit_rate,
        "net": format_decimal(total_net, decimal_places),
        "average_win": format_decimal(average_win, decimal_places),
        "average_loss": format_decimal(average_loss, decimal_places),
        "trend_direction": trend["direction"],
        "trend_arrow": trend["arrow"],
        "trend_label": trend["label"],
    }


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
        machine_payload = []
        for machine in config.machines:
            reel_positions = state.reel_positions.get(machine.key)
            if not isinstance(reel_positions, list) or len(reel_positions) != 3:
                reel_positions = list(default_reel_positions(machine))
            machine_payload.append(
                {
                    "key": machine.key,
                    "label": machine.label,
                    "profile_name": machine.slot_profile_name,
                    "reel_strip": list(build_reel_strip(machine)),
                    "reel_positions": reel_positions,
                }
            )

        return {
            "balance": format_decimal(state.balance, config.decimal_places),
            "last_result": state.last_result,
            "can_undo": bool(state.review_undo_stack and state.review_undo_stack[0]),
            "machines": machine_payload,
            "spin_animation_duration_ms": config.spin_animation_duration_ms,
            "spin_trigger_every_n": config.spin_trigger_every_n,
            "eligible_reviews_since_spin_check": (
                state.eligible_reviews_since_spin_check
            ),
            "stealth_mode_enabled": config.stealth_mode_enabled,
            "pending_stack_value": format_decimal(
                state.pending_stack_value,
                config.decimal_places,
            ),
            "card_id": card_id,
            "answer_button_count": answer_button_count,
            "tier_name": tier_name,
            "next_unlock_balance": (
                format_decimal(next_unlock, config.decimal_places)
                if next_unlock is not None
                else None
            ),
        }

    def apply_review(
        self, *, card_id: int, ease: int, button_count: int
    ) -> RoundSpinResult:
        config = self.config()
        state = self.state()
        previous_reel_positions = {
            key: list(value) for key, value in state.reel_positions.items()
        }
        previous_trigger_count = state.eligible_reviews_since_spin_check
        previous_pending_stack_value = state.pending_stack_value
        bet = quantize_decimal(REVIEW_BET, config.decimal_places)
        answer_key = answer_key_for_rating(ease, button_count)
        answer_value = _answer_base_value(config, answer_key)
        stacked_value = quantize_decimal(
            state.pending_stack_value + answer_value,
            config.decimal_places,
        )
        next_trigger_count = state.eligible_reviews_since_spin_check + 1
        should_settle_stack = next_trigger_count >= config.spin_trigger_every_n

        if not config.machines:
            return build_round_result(
                config,
                card_id=card_id,
                answer_key=answer_key,
                bet=bet,
                balance_before=state.balance,
                rng=self._rng,
                base_reward_override=(
                    stacked_value if should_settle_stack else answer_value
                ),
                payout_on_no_spin=should_settle_stack,
                stack_value_override=stacked_value,
            )
        today = datetime.now().astimezone().date().isoformat()
        did_spin = (
            _should_trigger_spin(
                stacked_value=stacked_value,
                config=config,
                rng=self._rng,
            )
            if should_settle_stack
            else False
        )
        result = build_round_result(
            config,
            card_id=card_id,
            answer_key=answer_key,
            bet=bet,
            balance_before=state.balance,
            rng=self._rng,
            previous_reel_positions_by_machine=state.reel_positions,
            did_spin_override=did_spin,
            base_reward_override=stacked_value if should_settle_stack else answer_value,
            payout_on_no_spin=should_settle_stack,
            stack_value_override=stacked_value,
        )
        next_trigger_count = 0 if should_settle_stack else next_trigger_count
        next_pending_stack_value = (
            Decimal("0") if should_settle_stack else stacked_value
        )
        dropped_history_event = (
            state.history[config.history_limit - 1]
            if len(state.history) >= config.history_limit
            else None
        )
        previous_undo_record = state.build_undo_record(
            config.decimal_places,
            review_day=today,
            dropped_history_event=dropped_history_event,
        )

        next_reel_positions = {
            key: list(value) for key, value in previous_reel_positions.items()
        }
        for machine_result in result.machine_results:
            machine_key = str(machine_result.get("machine_key", "")).strip()
            reel_positions = machine_result.get("reel_positions")
            if (
                machine_key
                and isinstance(reel_positions, list)
                and len(reel_positions) == 3
                and (
                    machine_result.get("did_spin")
                    or machine_key in previous_reel_positions
                )
            ):
                next_reel_positions[machine_key] = [
                    int(position) for position in reel_positions
                ]
        is_undoable = _is_undoable_slot_event(
            result=result,
            previous_reel_positions=previous_reel_positions,
            next_reel_positions=next_reel_positions,
            previous_trigger_count=previous_trigger_count,
            next_trigger_count=next_trigger_count,
        )
        if previous_pending_stack_value != next_pending_stack_value:
            is_undoable = True
        serialized_result = result.to_dict(config.decimal_places)
        serialized_result["history_format_version"] = HISTORY_FORMAT_VERSION
        serialized_result["slot_instance_key"] = addon_instance_key()
        serialized_result["slot_instance_label"] = addon_package_name()
        state.reel_positions = next_reel_positions
        state.eligible_reviews_since_spin_check = next_trigger_count
        state.pending_stack_value = next_pending_stack_value
        state.last_result = serialized_result

        if is_undoable:
            state.balance = result.balance_after
            state.spins += sum(
                1
                for machine_result in result.machine_results
                if machine_result.get("did_spin")
            )
            if result.net_change > Decimal("0"):
                state.total_won = quantize_decimal(
                    state.total_won + result.net_change,
                    config.decimal_places,
                )
                state.current_streak += 1
                state.best_streak = max(state.best_streak, state.current_streak)
                state.biggest_jackpot = max(state.biggest_jackpot, result.net_change)
            elif result.net_change < Decimal("0"):
                state.total_lost = quantize_decimal(
                    state.total_lost + abs(result.net_change),
                    config.decimal_places,
                )
                state.current_streak = 0
            else:
                state.current_streak = 0

            if result.net_change != Decimal("0"):
                state.daily_earnings[today] = quantize_decimal(
                    state.daily_earnings.get(today, Decimal("0")) + result.net_change,
                    config.decimal_places,
                )
            _prepend_capped(state.history, serialized_result, config.history_limit)
            _prepend_capped(
                state.undo_history,
                previous_undo_record,
                UNDO_HISTORY_LIMIT,
            )
        _prepend_capped(
            state.review_undo_stack,
            is_undoable,
            UNDO_HISTORY_LIMIT,
        )
        self._repository.save(state, config)
        return result

    def undo_last_review(self) -> bool:
        config = self.config()
        state = self.state()
        if not state.review_undo_stack:
            return False
        review_was_undoable = bool(state.review_undo_stack.pop(0))
        if not review_was_undoable:
            self._repository.save(state, config)
            return False
        if not state.undo_history:
            self._repository.save(state, config)
            return False

        previous_snapshot = state.undo_history.pop(0)
        state.restore_review_undo(previous_snapshot, config)
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
        graph_history = list(reversed(state.history[:1000]))
        recent_window = graph_history[-100:]
        answer_counts = {"again": 0, "hard": 0, "good": 0, "easy": 0}
        pair_hits = 0
        triple_hits = 0
        positive_spins = 0
        recent_positive_spins = 0
        recent_spin_count = 0
        win_events = 0
        loss_events = 0
        win_total = Decimal("0")
        loss_total = Decimal("0")
        best_win = Decimal("0")
        worst_loss = Decimal("0")

        if graph_history:
            balance_values = [
                Decimal(str(event.get("balance_after", "0"))) for event in graph_history
            ]
            recent_high_balance = max(balance_values)
            recent_low_balance = min(balance_values)
        else:
            recent_high_balance = state.balance
            recent_low_balance = state.balance

        for event in graph_history:
            answer_key = str(event.get("answer_key", ""))
            if answer_key in answer_counts:
                answer_counts[answer_key] += 1

            for machine_result in _machine_results_for_event(event):
                if machine_result.get("did_spin"):
                    if machine_result.get("line_hit"):
                        triple_hits += 1
                    elif machine_result.get("matched_symbol"):
                        pair_hits += 1
                    if Decimal(str(machine_result.get("payout", "0"))) > Decimal("0"):
                        positive_spins += 1

            net_change = Decimal(str(event.get("net_change", "0")))
            if net_change > Decimal("0"):
                win_events += 1
                win_total += net_change
                best_win = max(best_win, net_change)
            elif net_change < Decimal("0"):
                loss_events += 1
                loss_total += abs(net_change)
                worst_loss = max(worst_loss, abs(net_change))

        recent_net = Decimal("0")
        for event in recent_window:
            for machine_result in _machine_results_for_event(event):
                if machine_result.get("did_spin"):
                    recent_spin_count += 1
                    if Decimal(str(machine_result.get("payout", "0"))) > Decimal("0"):
                        recent_positive_spins += 1
            recent_net += Decimal(str(event.get("net_change", "0")))

        history_count = len(graph_history)
        today = datetime.now().astimezone().date().isoformat()
        today_net = quantize_decimal(
            state.daily_earnings.get(today, Decimal("0")),
            config.decimal_places,
        )
        lifetime_net = quantize_decimal(
            state.balance - config.starting_balance,
            config.decimal_places,
        )
        spin_win_rate = (
            round((positive_spins / state.spins) * 100, 1) if state.spins else 0.0
        )
        average_win = quantize_decimal(
            win_total / win_events if win_events else Decimal("0"),
            config.decimal_places,
        )
        average_loss = quantize_decimal(
            loss_total / loss_events if loss_events else Decimal("0"),
            config.decimal_places,
        )
        recent_100_net = quantize_decimal(recent_net, config.decimal_places)
        recent_100_spin_win_rate = (
            round((recent_positive_spins / recent_spin_count) * 100, 1)
            if recent_spin_count
            else 0.0
        )
        recent_10_summary = _recent_summary(
            graph_history,
            window_size=10,
            decimal_places=config.decimal_places,
        )
        recent_50_summary = _recent_summary(
            graph_history,
            window_size=50,
            decimal_places=config.decimal_places,
        )
        recent_100_summary = _recent_summary(
            graph_history,
            window_size=100,
            decimal_places=config.decimal_places,
        )
        session_temperature = _session_temperature(
            today_net=today_net,
            recent_trend=recent_10_summary["trend_direction"],
            current_streak=state.current_streak,
        )
        volatility_label = _volatility_label(
            average_win=average_win,
            best_win=best_win,
            worst_loss=worst_loss,
        )

        return {
            "balance": format_decimal(state.balance, config.decimal_places),
            "machines": [
                {
                    "key": machine.key,
                    "label": machine.label,
                    "profile_name": machine.slot_profile_name,
                }
                for machine in config.machines
            ],
            "today_net": format_decimal(today_net, config.decimal_places),
            "review_stake": format_decimal(REVIEW_BET, config.decimal_places),
            "total_won": format_decimal(state.total_won, config.decimal_places),
            "total_lost": format_decimal(state.total_lost, config.decimal_places),
            "lifetime_net": format_decimal(lifetime_net, config.decimal_places),
            "spins": state.spins,
            "current_streak": state.current_streak,
            "streak_context": _streak_context(state.current_streak),
            "best_streak": state.best_streak,
            "biggest_jackpot": format_decimal(
                state.biggest_jackpot,
                config.decimal_places,
            ),
            "last_result": state.last_result,
            "session_temperature": session_temperature,
            "history_count": history_count,
            "spin_win_rate": spin_win_rate,
            "pair_hits": pair_hits,
            "triple_hits": triple_hits,
            "answer_counts": answer_counts,
            "average_win": format_decimal(average_win, config.decimal_places),
            "average_loss": format_decimal(average_loss, config.decimal_places),
            "best_win": format_decimal(best_win, config.decimal_places),
            "worst_loss": format_decimal(worst_loss, config.decimal_places),
            "recent_100_net": format_decimal(recent_100_net, config.decimal_places),
            "recent_100_spin_win_rate": recent_100_spin_win_rate,
            "recent_10": recent_10_summary,
            "recent_50": recent_50_summary,
            "recent_100": recent_100_summary,
            "recent_high_balance": format_decimal(
                recent_high_balance,
                config.decimal_places,
            ),
            "recent_low_balance": format_decimal(
                recent_low_balance,
                config.decimal_places,
            ),
            "volatility_label": volatility_label,
            "history": state.history[:20],
            "graph_history": graph_history,
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
