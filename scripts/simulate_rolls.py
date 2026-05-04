#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from anki_slot_machine.config import SlotMachineConfig, config_from_raw
from anki_slot_machine.decimal_utils import ZERO, format_decimal, quantize_decimal, to_decimal
from anki_slot_machine.game import build_round_result_explicit


CONFIG_PATH = ROOT / "src" / "anki_slot_machine" / "config.json"
PACKAGE_DIR = ROOT / "src" / "anki_slot_machine"
REVIEW_BET = Decimal("1")


@dataclass(frozen=True)
class SimulationResult:
    rolls: int
    seed: int
    starting_balance: Decimal
    ending_balance: Decimal
    net_change: Decimal
    total_won: Decimal
    total_lost: Decimal
    total_roll_cost: Decimal
    spin_count: int
    hit_count: int
    answer_counts: dict[str, int]
    highest_balance: Decimal
    lowest_balance: Decimal

    def to_dict(self, decimal_places: int) -> dict[str, object]:
        return {
            "rolls": self.rolls,
            "seed": self.seed,
            "starting_balance": format_decimal(self.starting_balance, decimal_places),
            "ending_balance": format_decimal(self.ending_balance, decimal_places),
            "net_change": format_decimal(self.net_change, decimal_places),
            "total_won": format_decimal(self.total_won, decimal_places),
            "total_lost": format_decimal(self.total_lost, decimal_places),
            "total_roll_cost": format_decimal(self.total_roll_cost, decimal_places),
            "spin_count": self.spin_count,
            "hit_count": self.hit_count,
            "answer_counts": dict(self.answer_counts),
            "highest_balance": format_decimal(self.highest_balance, decimal_places),
            "lowest_balance": format_decimal(self.lowest_balance, decimal_places),
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run repeated slot-machine simulations with configurable answer mix.",
    )
    parser.add_argument("--rolls", type=int, default=1000, help="Rolls per simulation run.")
    parser.add_argument("--runs", type=int, default=1000, help="Number of simulation runs.")
    parser.add_argument("--starting-balance", type=Decimal, default=Decimal("100"))
    parser.add_argument("--again", type=Decimal, default=Decimal("0"))
    parser.add_argument("--hard", type=Decimal, default=Decimal("0"))
    parser.add_argument("--good", type=Decimal, default=Decimal("1"))
    parser.add_argument("--easy", type=Decimal, default=Decimal("0"))
    parser.add_argument(
        "--seed-start",
        type=int,
        default=0,
        help="First seed; each run uses seed_start + run_index.",
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=5,
        help="How many individual runs to print after the summary.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=CONFIG_PATH,
        help="Optional config JSON path.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print a JSON summary instead of text.",
    )
    return parser.parse_args()


def load_config(config_path: Path) -> SlotMachineConfig:
    raw = json.loads(config_path.read_text(encoding="utf-8"))
    return config_from_raw(raw, base_dir=PACKAGE_DIR)


def answer_value(config: SlotMachineConfig, answer_key: str) -> Decimal:
    fallback = {
        "again": Decimal("0"),
        "hard": Decimal("0.5"),
        "good": Decimal("1"),
        "easy": Decimal("1.5"),
    }[answer_key]
    return quantize_decimal(
        config.answer_base_values.get(answer_key, fallback),
        config.decimal_places,
    )


def normalized_weights(args: argparse.Namespace) -> tuple[tuple[str, ...], tuple[float, ...]]:
    raw_weights = {
        "again": max(ZERO, to_decimal(args.again)),
        "hard": max(ZERO, to_decimal(args.hard)),
        "good": max(ZERO, to_decimal(args.good)),
        "easy": max(ZERO, to_decimal(args.easy)),
    }
    total = sum(raw_weights.values(), ZERO)
    if total <= ZERO:
        raise ValueError("At least one of again/hard/good/easy must be greater than zero.")
    answer_keys = tuple(raw_weights.keys())
    return answer_keys, tuple(float(raw_weights[key]) for key in answer_keys)


def simulate_once(
    *,
    config: SlotMachineConfig,
    rolls: int,
    starting_balance: Decimal,
    seed: int,
    answer_keys: tuple[str, ...],
    weights: tuple[float, ...],
) -> SimulationResult:
    if rolls < 0:
        raise ValueError("rolls must be greater than or equal to zero.")

    rng = random.Random(seed)
    state = SimpleNamespace(
        balance=quantize_decimal(starting_balance, config.decimal_places),
        pending_stack_value=Decimal("0"),
        pending_roll_cost=Decimal("0"),
        pending_roll_cost_by_machine={},
        eligible_reviews_since_spin_check=0,
        reel_positions={},
    )
    bet = quantize_decimal(REVIEW_BET, config.decimal_places)

    answer_counts = {key: 0 for key in answer_keys}
    total_won = Decimal("0")
    total_lost = Decimal("0")
    total_roll_cost = Decimal("0")
    spin_count = 0
    hit_count = 0
    highest_balance = state.balance
    lowest_balance = state.balance

    for card_id in range(1, rolls + 1):
        answer_key = rng.choices(answer_keys, weights=weights, k=1)[0]
        answer_counts[answer_key] += 1
        base_reward = answer_value(config, answer_key)
        stacked_value = quantize_decimal(
            state.pending_stack_value + base_reward,
            config.decimal_places,
        )
        next_trigger_count = state.eligible_reviews_since_spin_check + 1
        did_spin = next_trigger_count >= config.spin_trigger_every_n
        settlement_value = stacked_value if did_spin else base_reward

        result = build_round_result_explicit(
            config,
            card_id=card_id,
            answer_key=answer_key,
            bet=bet,
            balance_before=state.balance,
            did_spin=did_spin,
            base_reward=settlement_value,
            stack_value=stacked_value,
            roll_cost=config.roll_cost,
            pending_roll_cost=state.pending_roll_cost,
            rng=rng,
            previous_reel_positions_by_machine=state.reel_positions,
            pending_roll_cost_by_machine=state.pending_roll_cost_by_machine,
            payout_on_no_spin=False,
        )

        total_roll_cost = quantize_decimal(total_roll_cost + result.roll_cost, config.decimal_places)
        if result.net_change > ZERO:
            total_won = quantize_decimal(total_won + result.net_change, config.decimal_places)
        elif result.net_change < ZERO:
            total_lost = quantize_decimal(total_lost + abs(result.net_change), config.decimal_places)

        spin_count += sum(
            1 for machine_result in result.machine_results if machine_result.get("did_spin")
        )
        hit_count += sum(
            1 for machine_result in result.machine_results if machine_result.get("matched_symbol")
        )

        state.reel_positions = {
            str(machine_result.get("machine_key", "")): [
                int(position) for position in machine_result.get("reel_positions", [])
            ]
            for machine_result in result.machine_results
            if str(machine_result.get("machine_key", "")).strip()
            and isinstance(machine_result.get("reel_positions"), list)
            and len(machine_result.get("reel_positions", [])) == 3
        }
        state.eligible_reviews_since_spin_check = 0 if did_spin else next_trigger_count
        state.pending_stack_value = Decimal("0") if did_spin else stacked_value
        event_pending_roll_cost = quantize_decimal(
            state.pending_roll_cost + result.roll_cost,
            config.decimal_places,
        )
        state.pending_roll_cost = Decimal("0") if did_spin else event_pending_roll_cost
        state.pending_roll_cost_by_machine = (
            {}
            if did_spin
            else {
                str(machine_result.get("machine_key", "")): Decimal(
                    str(machine_result.get("pending_roll_cost", "0"))
                )
                for machine_result in result.machine_results
                if str(machine_result.get("machine_key", "")).strip()
            }
        )
        state.balance = result.balance_after
        highest_balance = max(highest_balance, state.balance)
        lowest_balance = min(lowest_balance, state.balance)

    ending_balance = quantize_decimal(state.balance, config.decimal_places)
    starting_balance = quantize_decimal(starting_balance, config.decimal_places)
    return SimulationResult(
        rolls=rolls,
        seed=seed,
        starting_balance=starting_balance,
        ending_balance=ending_balance,
        net_change=quantize_decimal(ending_balance - starting_balance, config.decimal_places),
        total_won=total_won,
        total_lost=total_lost,
        total_roll_cost=total_roll_cost,
        spin_count=spin_count,
        hit_count=hit_count,
        answer_counts=answer_counts,
        highest_balance=highest_balance,
        lowest_balance=lowest_balance,
    )


def percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    index = int((len(ordered) - 1) * p)
    return ordered[index]


def build_summary(results: list[SimulationResult], decimal_places: int) -> dict[str, object]:
    ending = [float(result.ending_balance) for result in results]
    net = [float(result.net_change) for result in results]
    roll_costs = [float(result.total_roll_cost) for result in results]
    hit_counts = [result.hit_count for result in results]
    spin_counts = [result.spin_count for result in results]

    profitable = sum(1 for value in net if value > 0)
    breakeven_or_better = sum(1 for value in net if value >= 0)
    losses = sum(1 for value in net if value < 0)

    return {
        "runs": len(results),
        "mean_ending_balance": format_decimal(Decimal(str(statistics.mean(ending))), decimal_places),
        "median_ending_balance": format_decimal(Decimal(str(statistics.median(ending))), decimal_places),
        "mean_net_change": format_decimal(Decimal(str(statistics.mean(net))), decimal_places),
        "median_net_change": format_decimal(Decimal(str(statistics.median(net))), decimal_places),
        "best_net": format_decimal(Decimal(str(max(net))), decimal_places),
        "worst_net": format_decimal(Decimal(str(min(net))), decimal_places),
        "p10_net": format_decimal(Decimal(str(percentile(net, 0.10))), decimal_places),
        "p25_net": format_decimal(Decimal(str(percentile(net, 0.25))), decimal_places),
        "p75_net": format_decimal(Decimal(str(percentile(net, 0.75))), decimal_places),
        "p90_net": format_decimal(Decimal(str(percentile(net, 0.90))), decimal_places),
        "profit_rate": round(profitable / len(results), 4),
        "breakeven_or_better_rate": round(breakeven_or_better / len(results), 4),
        "loss_rate": round(losses / len(results), 4),
        "mean_total_roll_cost": format_decimal(Decimal(str(statistics.mean(roll_costs))), decimal_places),
        "mean_hit_count": round(statistics.mean(hit_counts), 2),
        "mean_spin_count": round(statistics.mean(spin_counts), 2),
    }


def print_text_report(
    *,
    args: argparse.Namespace,
    config: SlotMachineConfig,
    results: list[SimulationResult],
) -> None:
    summary = build_summary(results, config.decimal_places)
    print("Roll Simulation Report")
    print("======================")
    print(f"Runs: {args.runs}")
    print(f"Rolls per run: {args.rolls}")
    print(
        "Answer mix weights: "
        f"Again {args.again}, Hard {args.hard}, Good {args.good}, Easy {args.easy}"
    )
    print(f"Starting balance: ${format_decimal(args.starting_balance, config.decimal_places)}")
    print(f"Roll cost: ${format_decimal(config.roll_cost, config.decimal_places)}")
    print("")
    for key, value in summary.items():
        print(f"{key}: {value}")
    print("")
    print("Sample runs")
    print("-----------")
    for result in results[: max(0, args.samples)]:
        print(result.to_dict(config.decimal_places))


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    answer_keys, weights = normalized_weights(args)
    results = [
        simulate_once(
            config=config,
            rolls=args.rolls,
            starting_balance=args.starting_balance,
            seed=args.seed_start + index,
            answer_keys=answer_keys,
            weights=weights,
        )
        for index in range(args.runs)
    ]
    if args.json:
        payload = {
            "config": str(args.config),
            "rolls": args.rolls,
            "runs": args.runs,
            "starting_balance": format_decimal(args.starting_balance, config.decimal_places),
            "weights": {
                "again": str(args.again),
                "hard": str(args.hard),
                "good": str(args.good),
                "easy": str(args.easy),
            },
            "summary": build_summary(results, config.decimal_places),
            "samples": [
                result.to_dict(config.decimal_places)
                for result in results[: max(0, args.samples)]
            ],
        }
        print(json.dumps(payload, indent=2))
        return
    print_text_report(args=args, config=config, results=results)


if __name__ == "__main__":
    main()
