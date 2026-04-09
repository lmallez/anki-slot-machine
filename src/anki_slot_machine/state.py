from __future__ import annotations

import json
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

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
DECIMAL_STATE_FIELDS = (
    "balance",
    "total_won",
    "total_lost",
    "biggest_jackpot",
)


def _backup_path(path: Path) -> Path:
    return path.with_suffix(f"{path.suffix}.bak")


def _read_state_payload(path: Path) -> dict | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"[anki-slot-machine] Failed to read state file {path.name}: {exc}")
        return None
    return payload if isinstance(payload, dict) else None


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


def _normalize_daily_earnings(
    payload: dict | None,
    *,
    decimal_places: int,
) -> dict[str, str]:
    if not isinstance(payload, dict):
        return {}

    return {
        str(key): format_decimal(
            parse_stored_decimal(value, decimal_places),
            decimal_places,
        )
        for key, value in payload.items()
    }


def _normalize_history_payload(
    payload: list | None,
    *,
    decimal_places: int,
) -> list[dict]:
    if not isinstance(payload, list):
        return []

    return [
        normalized
        for item in payload
        if isinstance(item, dict)
        for normalized in [
            _normalize_event_payload(
                item,
                decimal_places=decimal_places,
            )
        ]
        if normalized is not None
    ]


def _normalize_state_snapshot_payload(
    payload: dict | None,
    *,
    decimal_places: int,
) -> dict | None:
    if not isinstance(payload, dict):
        return None

    normalized: dict[str, object] = {}
    for field_name in DECIMAL_STATE_FIELDS:
        normalized[field_name] = format_decimal(
            parse_stored_decimal(payload.get(field_name), decimal_places),
            decimal_places,
        )

    normalized["spins"] = max(0, int(payload.get("spins", 0)))
    normalized["current_streak"] = max(0, int(payload.get("current_streak", 0)))
    normalized["best_streak"] = max(0, int(payload.get("best_streak", 0)))
    normalized["daily_earnings"] = _normalize_daily_earnings(
        payload.get("daily_earnings"),
        decimal_places=decimal_places,
    )
    normalized["history"] = _normalize_history_payload(
        payload.get("history"),
        decimal_places=decimal_places,
    )
    normalized["last_result"] = _normalize_event_payload(
        payload.get("last_result"),
        decimal_places=decimal_places,
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
    undo_history: list[dict] = field(default_factory=list)

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
                for key, value in _normalize_daily_earnings(
                    data.get("daily_earnings"),
                    decimal_places=config.decimal_places,
                ).items()
            },
            history=_normalize_history_payload(
                data.get("history"),
                decimal_places=config.decimal_places,
            ),
            last_result=_normalize_event_payload(
                data.get("last_result"),
                decimal_places=config.decimal_places,
            ),
            undo_history=[
                normalized
                for item in data.get("undo_history") or []
                if isinstance(item, dict)
                for normalized in [
                    _normalize_state_snapshot_payload(
                        item,
                        decimal_places=config.decimal_places,
                    )
                ]
                if normalized is not None
            ],
        )
        return state

    def review_snapshot(self, decimal_places: int) -> dict:
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

    def restore_review_snapshot(
        self,
        payload: dict,
        config: SlotMachineConfig,
    ) -> None:
        restored = SlotMachineState.from_dict(payload, config)
        self.balance = restored.balance
        self.total_won = restored.total_won
        self.total_lost = restored.total_lost
        self.spins = restored.spins
        self.current_streak = restored.current_streak
        self.best_streak = restored.best_streak
        self.biggest_jackpot = restored.biggest_jackpot
        self.daily_earnings = restored.daily_earnings
        self.history = restored.history
        self.last_result = restored.last_result

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
            "undo_history": self.undo_history,
        }


class StateRepository:
    def load(self, config: SlotMachineConfig) -> SlotMachineState:
        path = state_path()
        backup = _backup_path(path)
        for candidate in (path, backup):
            if not candidate.exists():
                continue
            payload = _read_state_payload(candidate)
            if payload is not None:
                return SlotMachineState.from_dict(payload, config)
        if path.exists() or backup.exists():
            print("[anki-slot-machine] Falling back to a fresh local slot state.")
            return SlotMachineState.initial(config)
        return SlotMachineState.initial(config)

    def save(self, state: SlotMachineState, config: SlotMachineConfig) -> None:
        path = state_path()
        backup = _backup_path(path)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            payload = (
                json.dumps(
                    state.to_dict(config.decimal_places),
                    indent=2,
                    ensure_ascii=False,
                )
                + "\n"
            )
            path.write_text(payload, encoding="utf-8")
            backup.write_text(payload, encoding="utf-8")
        except OSError as exc:
            print(f"[anki-slot-machine] Failed to save state file: {exc}")
