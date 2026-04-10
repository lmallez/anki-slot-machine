from __future__ import annotations

import copy
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
UNDO_FORMAT_VERSION = 1
UNDO_HISTORY_LIMIT = 20
BACKUP_SAVE_INTERVAL = 20


def _normalize_reel_positions_entry(value) -> list[int] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        return None
    normalized: list[int] = []
    for item in value[:3]:
        try:
            normalized.append(max(0, int(item)))
        except (TypeError, ValueError):
            normalized.append(0)
    return normalized


def _normalize_reel_positions_map(payload) -> dict[str, list[int]]:
    if not isinstance(payload, dict):
        return {}
    normalized: dict[str, list[int]] = {}
    for key, value in payload.items():
        entry = _normalize_reel_positions_entry(value)
        if entry is not None:
            normalized[str(key)] = entry
    return normalized


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
    raw_machine_results = normalized.get("machine_results")
    if isinstance(raw_machine_results, list):
        normalized["machine_results"] = [
            machine_result
            for item in raw_machine_results
            if isinstance(item, dict)
            for machine_result in [
                _normalize_event_payload(
                    item,
                    decimal_places=decimal_places,
                )
            ]
            if machine_result is not None
        ]
    for field_name in ("reel_start_positions", "reel_positions", "reel_step_counts"):
        if field_name in normalized:
            entry = _normalize_reel_positions_entry(normalized.get(field_name))
            if entry is not None:
                normalized[field_name] = entry
    if "no_spin" in normalized:
        normalized["no_spin"] = bool(normalized.get("no_spin"))
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
    normalized["reel_positions"] = _normalize_reel_positions_map(
        payload.get("reel_positions"),
    )
    normalized["eligible_reviews_since_spin_check"] = max(
        0,
        int(payload.get("eligible_reviews_since_spin_check", 0)),
    )
    return normalized


def _normalize_undo_record_payload(
    payload: dict | None,
    *,
    decimal_places: int,
) -> dict | None:
    if not isinstance(payload, dict):
        return None
    if int(payload.get("undo_format_version", 0) or 0) != UNDO_FORMAT_VERSION:
        return None

    normalized: dict[str, object] = {
        "undo_format_version": UNDO_FORMAT_VERSION,
    }
    for field_name in DECIMAL_STATE_FIELDS:
        normalized[field_name] = format_decimal(
            parse_stored_decimal(payload.get(field_name), decimal_places),
            decimal_places,
        )

    normalized["spins"] = max(0, int(payload.get("spins", 0)))
    normalized["current_streak"] = max(0, int(payload.get("current_streak", 0)))
    normalized["best_streak"] = max(0, int(payload.get("best_streak", 0)))

    review_day = str(payload.get("daily_earnings_date") or "").strip()
    had_daily_entry = bool(payload.get("had_daily_earnings_entry"))
    normalized["daily_earnings_date"] = review_day
    normalized["had_daily_earnings_entry"] = had_daily_entry
    normalized["daily_earnings_previous_value"] = (
        format_decimal(
            parse_stored_decimal(
                payload.get("daily_earnings_previous_value"),
                decimal_places,
            ),
            decimal_places,
        )
        if review_day and had_daily_entry
        else None
    )
    normalized["last_result"] = _normalize_event_payload(
        payload.get("last_result"),
        decimal_places=decimal_places,
    )
    normalized["reel_positions"] = _normalize_reel_positions_map(
        payload.get("reel_positions"),
    )
    normalized["eligible_reviews_since_spin_check"] = max(
        0,
        int(payload.get("eligible_reviews_since_spin_check", 0)),
    )
    normalized["dropped_history_event"] = _normalize_event_payload(
        payload.get("dropped_history_event"),
        decimal_places=decimal_places,
    )
    return normalized


def _normalize_undo_history_payload(
    payload: list | None,
    *,
    decimal_places: int,
) -> tuple[list[dict], list[bool]]:
    if not isinstance(payload, list):
        return [], []

    normalized_entries: list[dict] = []
    keep_flags: list[bool] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        normalized = _normalize_undo_record_payload(
            item,
            decimal_places=decimal_places,
        )
        keep_flags.append(normalized is not None)
        if normalized is not None:
            normalized_entries.append(normalized)
    return normalized_entries, keep_flags


def _normalize_review_undo_stack_payload(
    payload,
    *,
    undo_keep_flags: list[bool] | None = None,
) -> list[bool]:
    if not isinstance(payload, list):
        return []

    normalized: list[bool] = []
    for item in payload:
        normalized.append(bool(item))

    if undo_keep_flags is None:
        return normalized

    filtered: list[bool] = []
    undo_index = 0
    # Only undoable reviews consume an undo-history entry, so keep the boolean
    # stack aligned with the compact undo records that survived normalization.
    for entry in normalized:
        if not entry:
            filtered.append(False)
            continue
        if undo_index >= len(undo_keep_flags):
            continue
        keep_entry = undo_keep_flags[undo_index]
        undo_index += 1
        if keep_entry:
            filtered.append(True)
    return filtered


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
    reel_positions: dict[str, list[int]] = field(default_factory=dict)
    eligible_reviews_since_spin_check: int = 0
    undo_history: list[dict] = field(default_factory=list)
    review_undo_stack: list[bool] = field(default_factory=list)

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
        undo_history, undo_keep_flags = _normalize_undo_history_payload(
            data.get("undo_history"),
            decimal_places=config.decimal_places,
        )
        review_undo_stack = _normalize_review_undo_stack_payload(
            data.get("review_undo_stack"),
            undo_keep_flags=undo_keep_flags,
        )
        if not review_undo_stack and undo_history:
            review_undo_stack = [True] * len(undo_history)
        undo_history = undo_history[:UNDO_HISTORY_LIMIT]
        review_undo_stack = review_undo_stack[:UNDO_HISTORY_LIMIT]

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
            reel_positions=_normalize_reel_positions_map(data.get("reel_positions")),
            eligible_reviews_since_spin_check=max(
                0, int(data.get("eligible_reviews_since_spin_check", 0))
            ),
            undo_history=undo_history,
            review_undo_stack=review_undo_stack,
        )
        return state

    def build_undo_record(
        self,
        decimal_places: int,
        *,
        review_day: str,
        dropped_history_event: dict | None,
    ) -> dict:
        had_daily_entry = review_day in self.daily_earnings
        return {
            "undo_format_version": UNDO_FORMAT_VERSION,
            "balance": format_decimal(self.balance, decimal_places),
            "total_won": format_decimal(self.total_won, decimal_places),
            "total_lost": format_decimal(self.total_lost, decimal_places),
            "spins": self.spins,
            "current_streak": self.current_streak,
            "best_streak": self.best_streak,
            "biggest_jackpot": format_decimal(self.biggest_jackpot, decimal_places),
            "daily_earnings_date": review_day,
            "had_daily_earnings_entry": had_daily_entry,
            "daily_earnings_previous_value": (
                format_decimal(self.daily_earnings[review_day], decimal_places)
                if had_daily_entry
                else None
            ),
            "last_result": copy.deepcopy(self.last_result),
            "reel_positions": copy.deepcopy(self.reel_positions),
            "eligible_reviews_since_spin_check": self.eligible_reviews_since_spin_check,
            "dropped_history_event": copy.deepcopy(dropped_history_event),
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
        self.reel_positions = restored.reel_positions
        self.eligible_reviews_since_spin_check = (
            restored.eligible_reviews_since_spin_check
        )
        self.undo_history = restored.undo_history
        self.review_undo_stack = restored.review_undo_stack

    def restore_review_undo(
        self,
        payload: dict,
        config: SlotMachineConfig,
    ) -> None:
        normalized = _normalize_undo_record_payload(
            payload,
            decimal_places=config.decimal_places,
        )
        if normalized is None:
            self.restore_review_snapshot(payload, config)
            return

        self.balance = parse_stored_decimal(
            normalized.get("balance"),
            config.decimal_places,
        )
        self.total_won = parse_stored_decimal(
            normalized.get("total_won"),
            config.decimal_places,
        )
        self.total_lost = parse_stored_decimal(
            normalized.get("total_lost"),
            config.decimal_places,
        )
        self.spins = max(0, int(normalized.get("spins", 0)))
        self.current_streak = max(0, int(normalized.get("current_streak", 0)))
        self.best_streak = max(0, int(normalized.get("best_streak", 0)))
        self.biggest_jackpot = parse_stored_decimal(
            normalized.get("biggest_jackpot"),
            config.decimal_places,
        )
        self.last_result = normalized.get("last_result")
        self.reel_positions = _normalize_reel_positions_map(
            normalized.get("reel_positions"),
        )
        self.eligible_reviews_since_spin_check = max(
            0,
            int(normalized.get("eligible_reviews_since_spin_check", 0)),
        )

        review_day = str(normalized.get("daily_earnings_date") or "").strip()
        had_daily_entry = bool(normalized.get("had_daily_earnings_entry"))
        if review_day:
            if had_daily_entry:
                self.daily_earnings[review_day] = parse_stored_decimal(
                    normalized.get("daily_earnings_previous_value"),
                    config.decimal_places,
                )
            else:
                self.daily_earnings.pop(review_day, None)

        restored_history = self.history[1:] if self.history else []
        dropped_history_event = normalized.get("dropped_history_event")
        if isinstance(dropped_history_event, dict):
            restored_history = [
                *restored_history,
                copy.deepcopy(dropped_history_event),
            ]
        self.history = restored_history[: config.history_limit]

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
            "reel_positions": self.reel_positions,
            "eligible_reviews_since_spin_check": self.eligible_reviews_since_spin_check,
            "undo_history": self.undo_history,
            "review_undo_stack": self.review_undo_stack,
        }


class StateRepository:
    def __init__(self) -> None:
        self._saves_since_backup = BACKUP_SAVE_INTERVAL

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
            payload = json.dumps(
                state.to_dict(config.decimal_places),
                ensure_ascii=False,
                separators=(",", ":"),
            )
            path.write_text(payload, encoding="utf-8")
            self._saves_since_backup += 1
            if not backup.exists() or self._saves_since_backup >= BACKUP_SAVE_INTERVAL:
                backup.write_text(payload, encoding="utf-8")
                self._saves_since_backup = 0
        except OSError as exc:
            print(f"[anki-slot-machine] Failed to save state file: {exc}")
