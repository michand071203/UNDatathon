from enum import Enum
from typing import Any, Optional

from nlp_service import (
    QueryFilter,
    NumericCondition,
    ListCondition,
    StringCondition,
    EnumCondition,
    OrderCondition,
)
from field_labels import FIELD_LABELS

OPERATOR_DISPLAY = {
    "eq": "=",
    "gt": ">",
    "lt": "<",
    "gte": "≥",
    "lte": "≤",
}


def _chip_item(label: str, field_name: str, index: Optional[int] = None) -> dict[str, Any]:
    return {
        "label": label,
        "field": field_name,
        "index": index,
    }


def _field_label(field_name: str) -> str:
    field_labels = FIELD_LABELS.get(field_name)
    if field_labels:
        return field_labels["short"]
    return field_name.replace("_", " ").title()


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
    if field_name == "limit" and isinstance(condition, int):
        return f"{_field_label(field_name)}: {condition}"

    if isinstance(condition, NumericCondition):
        op = OPERATOR_DISPLAY.get(condition.operator, condition.operator)
        val = _format_numeric_value(field_name, condition.value)
        return f"{_field_label(field_name)} {op} {val}"

    if isinstance(condition, StringCondition):
        return f"Match {_field_label(field_name)}: {condition.value}"

    if isinstance(condition, (ListCondition, EnumCondition)):
        prefix = "Excluding" if condition.exclude else "In"
        values = ", ".join(_format_list_value(v) for v in condition.values)
        if field_name == "locations":
            return f"{prefix}: {values}"
        return f"{prefix} {_field_label(field_name)}: {values}"

    if isinstance(condition, OrderCondition):
        return f"Sort: {_field_label(condition.field)} ({condition.direction})"

    return None


def build_filter_chips(parsed_filter: QueryFilter, chip_field_order: list[str]) -> list[dict[str, Any]]:
    chips: list[dict[str, Any]] = []

    for field_name in chip_field_order:
        condition = getattr(parsed_filter, field_name, None)
        if condition is None:
            continue

        if field_name == "limit" and isinstance(condition, int):
            if parsed_filter.order_by and parsed_filter.order_by.field:
                sort_label = _field_label(parsed_filter.order_by.field)
                chips.append(_chip_item(f"Top {sort_label}: {condition}", field_name))
            else:
                chips.append(_chip_item(f"{_field_label(field_name)}: {condition}", field_name))
            continue

        if isinstance(condition, list):
            for idx, item in enumerate(condition):
                chip = _build_chip(field_name, item)
                if chip:
                    chips.append(_chip_item(chip, field_name, idx))
            continue

        chip = _build_chip(field_name, condition)
        if chip:
            chips.append(_chip_item(chip, field_name))

    return chips
