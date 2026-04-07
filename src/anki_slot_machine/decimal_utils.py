from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

ZERO = Decimal("0")
ONE = Decimal("1")
THREE = Decimal("3")


def to_decimal(value, default: Decimal = ZERO) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if value is None:
        return default
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return default


def decimal_places_value(value, default: int = 2) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return max(0, default)


def quantum_for_places(decimal_places: int) -> Decimal:
    places = decimal_places_value(decimal_places)
    if places == 0:
        return ONE
    return ONE.scaleb(-places)


def quantize_decimal(value, decimal_places: int) -> Decimal:
    return to_decimal(value).quantize(
        quantum_for_places(decimal_places),
        rounding=ROUND_HALF_UP,
    )


def parse_stored_decimal(value, decimal_places: int, default: str = "0") -> Decimal:
    return quantize_decimal(to_decimal(value, to_decimal(default)), decimal_places)


def format_decimal(value, decimal_places: int) -> str:
    quantized = quantize_decimal(value, decimal_places)
    places = decimal_places_value(decimal_places)
    if places == 0:
        return f"{quantized:.0f}"
    return f"{quantized:.{places}f}"
