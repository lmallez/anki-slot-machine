from __future__ import annotations

import json
from dataclasses import dataclass, field
from decimal import Decimal

from .config import SlotMachineConfig
from .decimal_utils import format_decimal, parse_stored_decimal
from .runtime import state_path

DECIMAL_EVENT_FIELDS = (
    "bet",
    "payout",
    "base_reward",
    "slot_bonus",
    "net_change",
    "balance_after",
    "slot_multiplier",
)


def _normalize_event_payload(
    payload: dict | None,
    *,
    decimal_places: int,
) -> dict | None:
    if not isinstance(payload, dict):
        return None

    normalized = dict(payload)
    for field_name in DECIMAL_EVENT_FIELDS:
        if field_name not in normalized:
            continue
        normalized[field_name] = format_decimal(
            parse_stored_decimal(normalized.get(field_name), decimal_places),
            decimal_places,
        )
    return normalized


@dataclass
class SlotMachineState:
    balance: Decimal
    total_won: Decimal = Decimal("0")
    total_lost: Decimal = Decimal("0")
    spins: int = 0
    current_streak: int = 0
    best_streak: int = 0
    biggest_jackpot: Decimal = Decimal("0")
    daily_earnings: dict[str, Decimal] = field(default_factory=dict)
    history: list[dict] = field(default_factory=list)
    last_result: dict | None = None

    @classmethod
    def initial(cls, config: SlotMachineConfig) -> "SlotMachineState":
        return cls(balance=config.starting_balance)

    @classmethod
    def from_dict(
        cls, data: dict | None, config: SlotMachineConfig
    ) -> "SlotMachineState":
        if not isinstance(data, dict):
            return cls.initial(config)

        initial = cls.initial(config)
        state = cls(
            balance=parse_stored_decimal(
                data.get("balance"),
                config.decimal_places,
                default=str(initial.balance),
            ),
            total_won=parse_stored_decimal(
                data.get("total_won"),
                config.decimal_places,
            ),
            total_lost=parse_stored_decimal(
                data.get("total_lost"),
                config.decimal_places,
            ),
            spins=max(0, int(data.get("spins", 0))),
            current_streak=max(0, int(data.get("current_streak", 0))),
            best_streak=max(0, int(data.get("best_streak", 0))),
            biggest_jackpot=parse_stored_decimal(
                data.get("biggest_jackpot"),
                config.decimal_places,
            ),
            daily_earnings={
                str(key): parse_stored_decimal(value, config.decimal_places)
                for key, value in (data.get("daily_earnings") or {}).items()
            },
            history=[
                normalized
                for item in data.get("history") or []
                if isinstance(item, dict)
                for normalized in [
                    _normalize_event_payload(
                        item,
                        decimal_places=config.decimal_places,
                    )
                ]
                if normalized is not None
            ],
            last_result=_normalize_event_payload(
                data.get("last_result"),
                decimal_places=config.decimal_places,
            ),
        )
        return state

    def to_dict(self, decimal_places: int) -> dict:
        return {
            "balance": format_decimal(self.balance, decimal_places),
            "total_won": format_decimal(self.total_won, decimal_places),
            "total_lost": format_decimal(self.total_lost, decimal_places),
            "spins": self.spins,
            "current_streak": self.current_streak,
            "best_streak": self.best_streak,
            "biggest_jackpot": format_decimal(self.biggest_jackpot, decimal_places),
            "daily_earnings": {
                key: format_decimal(value, decimal_places)
                for key, value in self.daily_earnings.items()
            },
            "history": self.history,
            "last_result": self.last_result,
        }


class StateRepository:
    def load(self, config: SlotMachineConfig) -> SlotMachineState:
        path = state_path()
        if not path.exists():
            return SlotMachineState.initial(config)

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            print(f"[anki-slot-machine] Failed to read state file: {exc}")
            return SlotMachineState.initial(config)

        return SlotMachineState.from_dict(payload, config)

    def save(self, state: SlotMachineState, config: SlotMachineConfig) -> None:
        path = state_path()
        try:
            path.write_text(
                json.dumps(
                    state.to_dict(config.decimal_places),
                    indent=2,
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
        except OSError as exc:
            print(f"[anki-slot-machine] Failed to save state file: {exc}")
