from typing import Any, Optional


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
    if points and points[-1][2] is not None:
        latest_percent = points[-1][1]
        latest_avg = points[-1][2]
        latest_below_peer = latest_percent + 5 < latest_avg
        latest_at_or_above_peer = latest_percent >= latest_avg

    return {
        "trend": trend,
        "recent_delta": recent_delta,
        "latest_below_peer": latest_below_peer,
        "latest_at_or_above_peer": latest_at_or_above_peer,
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

    requirements_value = crisis.get("requirements")
    funding_value = crisis.get("funding")
    funding_gap = None
    if isinstance(requirements_value, (int, float)) and isinstance(funding_value, (int, float)):
        funding_gap = max(float(requirements_value) - float(funding_value), 0.0)

    timeline_summary = _summarize_funding_timeline(crisis.get("funding_timeline") or [])
    trend = timeline_summary["trend"]
    latest_below_peer = bool(timeline_summary["latest_below_peer"])
    latest_at_or_above_peer = bool(timeline_summary["latest_at_or_above_peer"])
    recent_delta = timeline_summary["recent_delta"]

    category_summary = _summarize_category_scores(crisis.get("category_scores") or {})
    category_max = category_summary["max_score"]
    category_avg = category_summary["avg_score"]
    category_high_count = int(category_summary["high_count"])
    category_severe_count = int(category_summary["severe_count"])
    category_top = category_summary["top_category"]

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

    risk_drivers: list[dict[str, Any]] = []
    positive_drivers: list[dict[str, Any]] = []
    financial_ratio_confidence: Optional[float] = None
    financial_gap_confidence: Optional[float] = None

    def add_driver(
        bucket: list[dict[str, Any]],
        label: str,
        confidence: float,
        kind: str,
    ) -> None:
        bucket.append({
            "label": label,
            "confidence": max(0.0, min(1.0, confidence)),
            "kind": kind,
        })

    if funding_ratio_value is not None:
        if funding_ratio_value < 10:
            financial_ratio_confidence = 0.95
        elif funding_ratio_value < 25:
            financial_ratio_confidence = 0.85
        elif funding_ratio_value < 45:
            financial_ratio_confidence = 0.62
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

    if latest_below_peer:
        if financial_ratio_confidence is None:
            financial_ratio_confidence = 0.74
        else:
            financial_ratio_confidence = max(financial_ratio_confidence, 0.74)
    elif latest_at_or_above_peer:
        add_driver(positive_drivers, "At or above peer benchmark", 0.61, "benchmark")

    if pin_value is not None:
        if pin_value >= 15_000_000:
            add_driver(risk_drivers, "V people in need", 0.84, "needs_scale")
        elif pin_value >= 7_000_000:
            add_driver(risk_drivers, "High people in need", 0.7, "needs_scale")
    else:
        add_driver(risk_drivers, "People-in-need data incomplete", 0.35, "needs_scale")

    if funding_gap is not None:
        if funding_gap >= 1_000_000_000:
            financial_gap_confidence = 0.8
        elif funding_gap >= 500_000_000:
            financial_gap_confidence = 0.6

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
            add_driver(positive_drivers, "Lower underfunding risk score", 0.55, "systematic_underfunding_score")

    if financial_ratio_confidence is not None or financial_gap_confidence is not None:
        ratio_conf = financial_ratio_confidence if financial_ratio_confidence is not None else -1.0
        gap_conf = financial_gap_confidence if financial_gap_confidence is not None else -1.0
        if gap_conf > ratio_conf:
            add_driver(risk_drivers, "Large funding gap", gap_conf, "financial_pressure")
        else:
            add_driver(risk_drivers, "Critically low funding ratio", ratio_conf, "financial_pressure")

    category_label_map = {
        "education": "education deprivation",
        "food_security": "food insecurity",
        "health": "health vulnerability",
        "hygiene": "sanitation stress",
        "protection": "protection risk",
    }
    if category_summary["available"]:
        if category_max is not None and category_max >= 90:
            top_name = category_label_map.get(category_top, "sectoral stress")
            add_driver(risk_drivers, f"Severe {top_name}", 0.88, "sector")
        elif category_max is not None and category_max >= 80:
            top_name = category_label_map.get(category_top, "sectoral stress")
            add_driver(risk_drivers, f"High {top_name}", 0.76, "sector")

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

    selected_drivers: list[str] = []
    selected_driver_confidence: list[dict[str, Any]] = []
    seen_families: set[str] = set()

    # First pass: maximize evidence diversity by selecting at most one driver per family.
    for item in ordered:
        label = item["label"]
        kind = item.get("kind", "other")
        family = kind_to_family.get(kind, kind)
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
            if label in selected_drivers or family in seen_families:
                continue
            selected_drivers.append(label)
            selected_driver_confidence.append(item)
            seen_families.add(family)
            if len(selected_drivers) == 3:
                break

    if len(selected_drivers) < 2:
        fallback_label = (
            "Data-limited assessment"
            if band != "Adequately Supported"
            else "No strong underfunding signals"
        )
        if fallback_label not in selected_drivers:
            selected_drivers.append(fallback_label)
            selected_driver_confidence.append({"label": fallback_label, "confidence": 0.35})

    return band, selected_drivers[:3], selected_driver_confidence[:3]