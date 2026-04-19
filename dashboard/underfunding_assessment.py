from typing import Any, Literal, Optional, TypedDict

from rationales import UNDERFUNDING_RATIONALE_SET, UnderfundingRationale


DriverKind = Literal[
    "funding_ratio",
    "trend",
    "history",
    "benchmark",
    "needs_scale",
    "data_completeness",
    "systematic_underfunding_score",
    "financial_pressure",
    "funding_gap",
    "sector",
]


class DriverEvidence(TypedDict):
    label: UnderfundingRationale
    confidence: float
    kind: DriverKind


def _get_nested_value(data: dict, path: list[str]) -> Any:
    current: Any = data
    for key in path:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return None
    return current


def _summarize_funding_timeline(funding_timeline: list[dict]) -> dict[str, Any]:
    points: list[tuple[int, float, Optional[float]]] = []
    for point in funding_timeline or []:
        year = point.get("year")
        percent = point.get("percent_funded")
        avg_percent = point.get("avg_percent_funded")
        if not isinstance(year, int) or not isinstance(percent, (int, float)):
            continue
        avg_value = float(avg_percent) if isinstance(avg_percent, (int, float)) else None
        points.append((year, float(percent), avg_value))

    points.sort(key=lambda item: item[0])

    trend = "insufficient"
    recent_delta = None
    if len(points) >= 2:
        # Prefer trend vs baseline average funding ratio when available.
        gap_points = [
            (year, percent - avg_percent)
            for year, percent, avg_percent in points
            if avg_percent is not None
        ]
        gap_points.sort(key=lambda item: item[0])

        if len(gap_points) >= 2:
            recent_delta = gap_points[-1][1] - gap_points[-2][1]
            if recent_delta <= -3:
                trend = "declining"
            elif recent_delta >= 3:
                trend = "improving"
            else:
                trend = "flat"
        else:
            recent_delta = points[-1][1] - points[-2][1]
            if recent_delta <= -5:
                trend = "declining"
            elif recent_delta >= 5:
                trend = "improving"
            else:
                trend = "flat"

    latest_below_peer = False
    latest_at_or_above_peer = False
    latest_gap_to_peer = None
    if points and points[-1][2] is not None:
        latest_percent = points[-1][1]
        latest_avg = points[-1][2]
        latest_gap_to_peer = latest_avg - latest_percent
        latest_below_peer = latest_percent + 5 < latest_avg
        latest_at_or_above_peer = latest_percent >= latest_avg

    return {
        "trend": trend,
        "recent_delta": recent_delta,
        "latest_below_peer": latest_below_peer,
        "latest_at_or_above_peer": latest_at_or_above_peer,
        "latest_gap_to_peer": latest_gap_to_peer,
    }


def _summarize_requirement_trend(funding_timeline: list[dict]) -> dict[str, Any]:
    # Prefer non-projected requirement points; fall back to all points when needed.
    confirmed_points: list[tuple[int, float]] = []
    all_points: list[tuple[int, float]] = []

    for point in funding_timeline or []:
        year = point.get("year")
        requirements = point.get("requirements")
        requirements_projected = bool(point.get("requirements_projected"))

        if not isinstance(year, int) or not isinstance(requirements, (int, float)):
            continue

        req_value = float(requirements)
        if req_value <= 0:
            continue

        all_points.append((year, req_value))
        if not requirements_projected:
            confirmed_points.append((year, req_value))

    points = confirmed_points if len(confirmed_points) >= 2 else all_points
    points.sort(key=lambda item: item[0])

    if len(points) < 2:
        return {
            "worsening": False,
            "recent_requirement_delta": None,
            "recent_requirement_growth_ratio": None,
        }

    prev_req = points[-2][1]
    latest_req = points[-1][1]
    recent_delta = latest_req - prev_req
    growth_ratio = (recent_delta / prev_req) if prev_req > 0 else None

    increase_steps = sum(1 for idx in range(1, len(points)) if points[idx][1] > points[idx - 1][1])
    worsening = False
    if recent_delta > 0:
        worsening = (recent_delta >= 25_000_000) or (
            growth_ratio is not None and growth_ratio >= 0.08
        )

    # Capture sustained upward demand even when the most recent jump is moderate.
    if not worsening and len(points) >= 3:
        worsening = increase_steps >= 2 and latest_req > points[0][1]

    return {
        "worsening": worsening,
        "recent_requirement_delta": recent_delta,
        "recent_requirement_growth_ratio": growth_ratio,
    }


def _summarize_category_scores(category_scores: Any) -> dict[str, Any]:
    if not isinstance(category_scores, dict):
        return {
            "available": False,
            "values": [],
            "max_score": None,
            "avg_score": None,
            "high_count": 0,
            "severe_count": 0,
            "top_category": None,
            "top_category_score": None,
        }

    valid_items: list[tuple[str, float]] = []
    for key, value in category_scores.items():
        if isinstance(value, (int, float)):
            valid_items.append((key, float(value)))

    if not valid_items:
        return {
            "available": False,
            "values": [],
            "max_score": None,
            "avg_score": None,
            "high_count": 0,
            "severe_count": 0,
            "top_category": None,
            "top_category_score": None,
        }

    values = [score for _, score in valid_items]
    top_category, top_score = max(valid_items, key=lambda item: item[1])

    return {
        "available": True,
        "values": values,
        "max_score": max(values),
        "avg_score": (sum(values) / len(values)),
        "high_count": sum(1 for score in values if score >= 75),
        "severe_count": sum(1 for score in values if score >= 85),
        "top_category": top_category,
        "top_category_score": top_score,
    }


def _summarize_cbpf_timeline(cbpf_timeline: list[dict]) -> dict[str, Any]:
    gap_points: list[tuple[int, float]] = []
    for point in cbpf_timeline or []:
        year = point.get("year")
        gap = point.get("gap")
        if not isinstance(year, int) or not isinstance(gap, (int, float)):
            continue
        gap_points.append((year, float(gap)))

    gap_points.sort(key=lambda item: item[0])
    latest_gap = gap_points[-1][1] if gap_points else None
    persistent_high_gap = False
    if len(gap_points) >= 2:
        persistent_high_gap = all(gap >= 0.75 for _, gap in gap_points[-2:])

    return {
        "latest_gap": latest_gap,
        "persistent_high_gap": persistent_high_gap,
        "years_with_gap": len(gap_points),
    }


def derive_underfunding_assessment(crisis: dict) -> tuple[str, list[str], list[dict[str, Any]]]:
    systematic_underfunding_score = _get_nested_value(crisis, ["systematic_underfunding", "score"])
    if not isinstance(systematic_underfunding_score, (int, float)):
        systematic_underfunding_score = None
    else:
        systematic_underfunding_score = float(systematic_underfunding_score)

    funding_ratio_percent = crisis.get("percent_funded")
    funding_ratio_value = (
        float(funding_ratio_percent)
        if isinstance(funding_ratio_percent, (int, float))
        else None
    )

    people_in_need = crisis.get("people_in_need")
    pin_value = float(people_in_need) if isinstance(people_in_need, (int, float)) else None

    required_funding = crisis.get("requirements")
    required_funding_projected = bool(crisis.get("requirements_projected"))
    funding_value = crisis.get("funding")
    funding_gap = None
    if isinstance(required_funding, (int, float)) and isinstance(funding_value, (int, float)):
        funding_gap = max(float(required_funding) - float(funding_value), 0.0)

    timeline_summary = _summarize_funding_timeline(crisis.get("funding_timeline") or [])
    trend = timeline_summary["trend"]
    latest_below_peer = bool(timeline_summary["latest_below_peer"])
    latest_at_or_above_peer = bool(timeline_summary["latest_at_or_above_peer"])
    latest_gap_to_peer = timeline_summary["latest_gap_to_peer"]
    recent_delta = timeline_summary["recent_delta"]

    requirement_summary = _summarize_requirement_trend(crisis.get("funding_timeline") or [])
    requirements_worsening = bool(requirement_summary["worsening"])
    recent_requirement_delta = requirement_summary["recent_requirement_delta"]
    recent_requirement_growth_ratio = requirement_summary["recent_requirement_growth_ratio"]

    category_summary = _summarize_category_scores(crisis.get("category_scores") or {})
    category_max = category_summary["max_score"]
    category_avg = category_summary["avg_score"]
    category_high_count = int(category_summary["high_count"])
    category_severe_count = int(category_summary["severe_count"])
    category_top = category_summary["top_category"]
    cbpf_summary = _summarize_cbpf_timeline(crisis.get("cbpf_timeline") or [])
    cbpf_gap_value = crisis.get("cbpf_gap")
    if not isinstance(cbpf_gap_value, (int, float)):
        cbpf_gap_value = cbpf_summary["latest_gap"]
    else:
        cbpf_gap_value = float(cbpf_gap_value)

    acute_underfunding = (
        (funding_ratio_value is not None and funding_ratio_value < 10)
        or (
            funding_ratio_value is not None
            and funding_ratio_value < 25
            and trend == "declining"
        )
        or (
            systematic_underfunding_score is not None
            and systematic_underfunding_score >= 85
        )
        or (category_max is not None and category_max >= 90)
        or (category_severe_count >= 2)
    )
    structural_scale_signal = (
        (pin_value is not None and pin_value >= 15_000_000)
        or (funding_gap is not None and funding_gap >= 1_000_000_000)
        or (category_avg is not None and category_avg >= 75)
        or (category_high_count >= 3)
    )

    if acute_underfunding and structural_scale_signal:
        band = "Critically Underfunded"
    elif acute_underfunding:
        band = "Significantly Underfunded"
    elif (
        (funding_ratio_value is not None and funding_ratio_value < 25)
        or trend == "declining"
        or latest_below_peer
        or (
            systematic_underfunding_score is not None
            and systematic_underfunding_score >= 60
        )
        or (pin_value is not None and pin_value >= 7_000_000)
        or (category_max is not None and category_max >= 80)
        or (category_avg is not None and category_avg >= 65)
    ):
        band = "Likely Underfunded"
    elif (
        funding_ratio_value is not None
        and funding_ratio_value >= 80
        and trend != "declining"
        and latest_at_or_above_peer
        and (
            systematic_underfunding_score is None
            or systematic_underfunding_score < 30
        )
        and (category_avg is None or category_avg < 55)
    ):
        band = "Adequately Supported"
    elif (
        funding_ratio_value is not None
        and funding_ratio_value >= 45
        and trend != "declining"
        and (
            systematic_underfunding_score is None
            or systematic_underfunding_score < 45
        )
        and (category_max is None or category_max < 70)
    ):
        band = "Some Funding Gaps"
    else:
        band = "Some Funding Gaps"

    risk_drivers: list[DriverEvidence] = []
    positive_drivers: list[DriverEvidence] = []
    financial_ratio_confidence: Optional[float] = None
    financial_ratio_label: Optional[UnderfundingRationale] = None
    financial_gap_confidence: Optional[float] = None
    financial_gap_label: Optional[UnderfundingRationale] = None

    def add_driver(
        bucket: list[DriverEvidence],
        label: UnderfundingRationale,
        confidence: float,
        kind: DriverKind,
    ) -> None:
        if label not in UNDERFUNDING_RATIONALE_SET:
            raise ValueError(f"Unsupported rationale label: {label}")
        bucket.append({
            "label": label,
            "confidence": max(0.0, min(1.0, confidence)),
            "kind": kind,
        })

    if funding_ratio_value is not None:
        if funding_ratio_value < 10:
            financial_ratio_label = "Critically low funding ratio"
            financial_ratio_confidence = 0.9
        elif funding_ratio_value < 25:
            financial_ratio_label = "Low funding ratio"
            financial_ratio_confidence = 0.78
        elif funding_ratio_value >= 45:
            add_driver(positive_drivers, "Strong current funding ratio", 0.72, "funding_ratio")
    else:
        add_driver(risk_drivers, "Funding ratio data incomplete", 0.35, "funding_ratio")

    if trend == "declining":
        delta_strength = 0.15
        if isinstance(recent_delta, (int, float)):
            delta_strength = min(0.3, abs(float(recent_delta)) / 40)
        add_driver(risk_drivers, "Declining funding trend", 0.68 + delta_strength, "trend")
    elif trend == "improving":
        delta_strength = 0.1
        if isinstance(recent_delta, (int, float)):
            delta_strength = min(0.24, abs(float(recent_delta)) / 45)
        add_driver(positive_drivers, "Improving funding trend", 0.58 + delta_strength, "trend")

    if requirements_worsening:
        worsening_confidence = 0.62
        if isinstance(recent_requirement_growth_ratio, (int, float)):
            worsening_confidence += min(0.22, max(0.0, float(recent_requirement_growth_ratio)))
        if isinstance(recent_requirement_delta, (int, float)):
            worsening_confidence += min(0.16, max(0.0, float(recent_requirement_delta)) / 1_000_000_000)
        add_driver(
            risk_drivers,
            "Worsening crisis",
            worsening_confidence,
            "history",
        )

    if latest_below_peer:
        if financial_ratio_confidence is None:
            financial_ratio_confidence = 0.74
        else:
            financial_ratio_confidence = max(financial_ratio_confidence, 0.74)
    elif latest_at_or_above_peer:
        add_driver(positive_drivers, "At or above peer benchmark", 0.61, "benchmark")

    # Peer gap can strengthen (or introduce) ratio pressure confidence.
    if isinstance(latest_gap_to_peer, (int, float)):
        if latest_gap_to_peer >= 20:
            financial_ratio_label = "Critically low funding ratio"
            if financial_ratio_confidence is None:
                financial_ratio_confidence = 0.9
            else:
                financial_ratio_confidence = max(financial_ratio_confidence, 0.9)
        elif latest_gap_to_peer >= 8:
            financial_ratio_label = "Low funding ratio"
            if financial_ratio_confidence is None:
                financial_ratio_confidence = 0.78
            else:
                financial_ratio_confidence = max(financial_ratio_confidence, 0.78)

    if pin_value is not None:
        if pin_value >= 15_000_000:
            add_driver(risk_drivers, "Very large impacted population", 0.84, "needs_scale")
        elif pin_value >= 7_000_000:
            add_driver(risk_drivers, "Large impacted population", 0.7, "needs_scale")

    if funding_gap is not None:
        if funding_gap >= 1_000_000_000:
            financial_gap_confidence = 0.8
            financial_gap_label = "Very large funding gap"
        elif funding_gap >= 500_000_000:
            financial_gap_confidence = 0.68
            financial_gap_label = "Large funding gap"
        elif funding_gap >= 250_000_000:
            financial_gap_confidence = 0.56
            financial_gap_label = "Material funding gap"

    if pin_value is None or required_funding_projected:
        incomplete_confidence = 0.9 if required_funding_projected else 0.35
        add_driver(risk_drivers, "Data-limited assessment", incomplete_confidence, "data_completeness")

    if systematic_underfunding_score is not None:
        if systematic_underfunding_score >= 85:
            if financial_ratio_confidence is None:
                financial_ratio_confidence = 0.86
            else:
                financial_ratio_confidence = max(financial_ratio_confidence, 0.86)
        elif systematic_underfunding_score >= 60:
            if financial_ratio_confidence is None:
                financial_ratio_confidence = 0.71
            else:
                financial_ratio_confidence = max(financial_ratio_confidence, 0.71)
        elif systematic_underfunding_score < 45:
            add_driver(positive_drivers, "Not systematically underfunded", 0.55, "systematic_underfunding_score")

    if financial_ratio_label is not None and financial_ratio_confidence is not None:
        add_driver(risk_drivers, financial_ratio_label, financial_ratio_confidence, "financial_pressure")
    if financial_gap_label is not None and financial_gap_confidence is not None:
        add_driver(risk_drivers, financial_gap_label, financial_gap_confidence, "funding_gap")

    if cbpf_summary["persistent_high_gap"]:
        add_driver(
            risk_drivers,
            "Persistently weak pooled-fund coverage",
            0.58,
            "history",
        )
    elif isinstance(cbpf_gap_value, float) and cbpf_gap_value >= 0.8:
        add_driver(
            risk_drivers,
            "Weak pooled-fund coverage",
            0.48,
            "history",
        )

    category_label_map: dict[str, tuple[UnderfundingRationale, UnderfundingRationale]] = {
        "education": ("Severe education deprivation", "High education deprivation"),
        "food_security": ("Severe food insecurity", "High food insecurity"),
        "health": ("Severe health vulnerability", "High health vulnerability"),
        "hygiene": ("Severe sanitation stress", "High sanitation stress"),
        "protection": ("Severe protection risk", "High protection risk"),
    }
    if category_summary["available"]:
        severe_label, high_label = category_label_map.get(
            str(category_top),
            ("Severe sectoral stress", "High sectoral stress"),
        )

        if category_max is not None and category_max >= 90:
            add_driver(risk_drivers, severe_label, 0.88, "sector")
        elif category_max is not None and category_max >= 80:
            add_driver(risk_drivers, high_label, 0.76, "sector")

        if category_high_count >= 3:
            add_driver(risk_drivers, "Broad multi-sector pressure", 0.82, "sector")
        elif category_high_count == 2:
            add_driver(risk_drivers, "Pressure across multiple sectors", 0.68, "sector")

        if category_avg is not None and category_avg >= 75:
            add_driver(risk_drivers, "High average sector severity", 0.79, "sector")
        elif category_avg is not None and category_avg < 55 and band == "Adequately Supported":
            add_driver(positive_drivers, "Lower sector severity", 0.64, "sector")

    if band == "Adequately Supported":
        ordered = sorted(positive_drivers, key=lambda item: item["confidence"], reverse=True)
    else:
        ordered = sorted(risk_drivers, key=lambda item: item["confidence"], reverse=True)

    kind_to_family = {
        "funding_ratio": "financial_pressure",
        "benchmark": "financial_pressure",
        "systematic_underfunding_score": "financial_pressure",
        "funding_gap": "financial_pressure",
        "trend": "trend",
        "needs_scale": "needs_scale",
        "sector": "sector",
        "history": "history",
    }

    selected_drivers: list[UnderfundingRationale] = []
    selected_driver_confidence: list[DriverEvidence] = []
    seen_families: set[str] = set()

    # First pass: maximize evidence diversity by selecting at most one driver per family.
    for item in ordered:
        label = item["label"]
        kind = item.get("kind", "other")
        family = kind_to_family.get(kind, kind)
        if not isinstance(family, str):
            family = "other"
        if label in selected_drivers or family in seen_families:
            continue
        selected_drivers.append(label)
        selected_driver_confidence.append(item)
        seen_families.add(family)
        if len(selected_drivers) == 3:
            break

    # Second pass: fill remaining slots with strongest remaining unique families.
    if len(selected_drivers) < 3:
        for item in ordered:
            label = item["label"]
            kind = item.get("kind", "other")
            family = kind_to_family.get(kind, kind)
            if not isinstance(family, str):
                family = "other"
            if label in selected_drivers or family in seen_families:
                continue
            selected_drivers.append(label)
            selected_driver_confidence.append(item)
            seen_families.add(family)
            if len(selected_drivers) == 3:
                break

    if len(selected_drivers) < 2 and band == "Adequately Supported":
        fallback_label: UnderfundingRationale = "No strong underfunding signals"
        if fallback_label not in selected_drivers:
            selected_drivers.append(fallback_label)
            selected_driver_confidence.append({"label": fallback_label, "confidence": 0.35})

    if len(selected_drivers) == 0 and band != "Adequately Supported":
        fallback_label = "Mixed or incomplete risk evidence"
        selected_drivers.append(fallback_label)
        selected_driver_confidence.append({"label": fallback_label, "confidence": 0.3})

    return band, [str(label) for label in selected_drivers[:3]], selected_driver_confidence[:3]

