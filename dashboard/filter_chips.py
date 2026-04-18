from enum import Enum
from typing import Any, Optional

from nlp_service import (
    QueryFilter,
    NumericCondition,
    ListCondition,
    EnumCondition,
    OrderCondition,
)

FIELD_LABELS = {
    "people_in_need": "PIN",
    "funding_coverage_percentage": "Funding",
    "crisis_type": "Crisis Type",
}

OPERATOR_DISPLAY = {
    "eq": "=",
    "gt": ">",
    "lt": "<",
    "gte": ">=",
    "lte": "<=",
}


def _field_label(field_name: str) -> str:
    return FIELD_LABELS.get(field_name, field_name.replace("_", " ").title())


def _format_numeric_value(field_name: str, value: float) -> str:
    if "percentage" in field_name:
        return f"{value:g}%"
    if float(value).is_integer():
        return f"{int(value):,}"
    return f"{value:g}"


def _format_list_value(value: Any) -> str:
    if isinstance(value, Enum):
        return str(value.value)
    return str(value)


def _build_chip(field_name: str, condition: Any) -> Optional[str]:
    if isinstance(condition, NumericCondition):
        op = OPERATOR_DISPLAY.get(condition.operator, condition.operator)
        val = _format_numeric_value(field_name, condition.value)
        return f"{_field_label(field_name)} {op} {val}"

    if isinstance(condition, (ListCondition, EnumCondition)):
        prefix = "Excluding" if condition.exclude else "In"
        values = ", ".join(_format_list_value(v) for v in condition.values)
        if field_name == "locations":
            return f"{prefix}: {values}"
        return f"{prefix} {_field_label(field_name)}: {values}"

    if isinstance(condition, OrderCondition):
        return f"Sort: {_field_label(condition.field)} ({condition.direction})"

    return None


def build_filter_chips(parsed_filter: QueryFilter, chip_field_order: list[str]) -> list[str]:
    chips: list[str] = []

    for field_name in chip_field_order:
        condition = getattr(parsed_filter, field_name, None)
        if condition is None:
            continue

        chip = _build_chip(field_name, condition)
        if chip:
            chips.append(chip)

    return chips
