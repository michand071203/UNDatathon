import re
import json
from pathlib import Path

import pandas as pd
import pycountry
from geopy.extra.rate_limiter import RateLimiter
from geopy.geocoders import Nominatim

DESCRIPTION_MAP = {
    "education": "education",
    "food security": "food_security",
    "food security and agriculture": "food_security",
    "sécurité alimentaire": "food_security",
    "health": "health",
    "santé": "health",
    "nutrition": "food_security",
    "protection": "protection",
    "protection (overall)": "protection",
    "wash": "hygiene",
    "water, sanitation and hygiene": "hygiene",
    "eau, hygiène et assainissement": "hygiene",
    "shelter": "shelter",
    "shelter and nfi": "shelter",
    "abris": "shelter",
    "cccm": "camp_coordination_and_camp_management",
    "camp coordination and camp management": "camp_coordination_and_camp_management",
    "multipurpose cash": "other",
    "multi-purpose cash": "other",
}

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
COORDINATE_FILE = DATA_DIR / "country_coordinates.csv"
COUNTRY_NAME_OVERRIDES = {
    "COD": "Democratic Republic of the Congo",
    "PSE": "Palestine",
}

COUNTRY_STITCHED_BASE_KEY_FAMILIES = {
    "SDN": {"HSDN", "CSDN", "CSDN1112", "FSDN0708", "OSDN"},
    "SYR": {"HSYR", "FSYR", "CSYR", "SSYR", "OSYR", "OSYR0809", "OSYR0910"},
}

GLOBAL_STITCHED_BASE_KEY_FAMILIES = {
    # Deprecated in favor of GLOBAL_STITCHED_BASE_KEY_RULES.
}

GLOBAL_STITCHED_BASE_KEY_RULES = [
    {
        "label": "SUDAN_REFUGEES",
        "name_norms": {"sudan emergency regional refugee response plan"},
        "base_keys": {"RRSDN", "RREGa"},
    },
    {
        "label": "SYRIA_REFUGEES",
        "name_norms": {
            "syrian arab republic regional refugee and resilience plan 3rp",
            "syria regional refugee response plan rrp",
        },
        "base_keys": {"RXSYRREG", "RSYR", "RJORLBNTUR"},
    },
    {
        "label": "VENEZUELA_RMRP",
        "name_norms": {"venezuela regional refugee and migrant response plan rmrp"},
        "base_keys": {"RREG", "RSAMR", "RREGb"},
    },
    {
        "label": "HOA_YEMEN_RMRP",
        "name_norms": {
            "regional migrant response plan for horn of africa to yemen and southern africa",
            "regional migrant response plan for the horn of africa and yemen",
        },
        "base_keys": {"RDJIETHSOM", "RDJIETHSOMYEM", "RRHOAY", "RREG"},
    },
    {
        "label": "SOUTH_SUDAN_RRP",
        "name_norms": {"south sudan regional refugee response plan"},
        "base_keys": {"RXSSDREG", "RSSDRRP", "RETHKENUGA"},
    },
    {
        "label": "DRC_RRP",
        "name_norms": {"democratic republic of the congo regional refugee response plan"},
        "base_keys": {"RDRCRRP", "RDRC_RRP"},
    },
    {
        "label": "AFGHAN_REGIONAL_REFUGEES",
        "name_norms": {"afghanistan situation regional refugee response plan"},
        "base_keys": {"RAFG", "RAFG_RRP", "RIRNPAK"},
    },
    {
        "label": "UGANDA_BURUNDI_RRP",
        "name_norms": {
            "burundi regional refugee response plan",
            "uganda regional refugee response plan",
        },
        "base_keys": {"RRWATZAUGA", "RUGA"},
    },
]

MONTHS_PATTERN = (
    r"january|february|march|april|may|june|july|august|"
    r"september|october|november|december"
)


def geocode_country(country_name, geocode, country_code=None):
    if not country_name:
        return None, None

    try:
        country_code = (country_code or "").lower()
        location = (
            geocode(country_name, country_codes=country_code) if country_code else None
        )
        if not location:
            location = geocode(country_name)
        if location:
            return float(location.latitude), float(location.longitude)
    except Exception:
        pass
    return None, None


def load_coordinates(primary_code_to_name):
    if COORDINATE_FILE.exists():
        coords = pd.read_csv(COORDINATE_FILE)
        if "ISO3" in coords.columns:
            coords = coords.rename(columns={"ISO3": "primary_location"})
    else:
        coords = pd.DataFrame(columns=["primary_location", "latitude", "longitude"])

    coords = coords[["primary_location", "latitude", "longitude"]]
    coords["latitude"] = pd.to_numeric(coords["latitude"], errors="coerce")
    coords["longitude"] = pd.to_numeric(coords["longitude"], errors="coerce")
    coords = coords[coords["primary_location"].notna()]

    # Keep one row per country, preferring rows that already have coordinates.
    coords["has_coordinates"] = coords["latitude"].notna() & coords["longitude"].notna()
    coords = coords.sort_values(by="has_coordinates")
    coords = coords.drop_duplicates(subset=["primary_location"], keep="last")
    coords = coords.drop(columns=["has_coordinates"])

    existing_with_coordinates = set(
        coords.loc[
            coords["latitude"].notna() & coords["longitude"].notna(), "primary_location"
        ]
    )
    primary_codes = list(primary_code_to_name.keys())
    missing_codes = [
        code for code in primary_codes if code not in existing_with_coordinates
    ]

    geolocator = Nominatim(user_agent="UNDatathonGeocoder/1.0")
    geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)

    for code in missing_codes:
        try:
            country = pycountry.countries.get(alpha_3=code)
        except LookupError:
            country = None
        country_code = getattr(country, "alpha_2", None)
        country_name = primary_code_to_name.get(code) or iso3_to_country_name(code)
        lat, lon = geocode_country(country_name, geocode, country_code=country_code)
        coords = coords[coords["primary_location"] != code]
        coords = pd.concat(
            [
                coords,
                pd.DataFrame(
                    [{"primary_location": code, "latitude": lat, "longitude": lon}]
                ),
            ],
            ignore_index=True,
        )

    # Keep file diffs stable by writing coordinates in alphabetical country-code order.
    coords = coords.sort_values(by="primary_location", kind="stable", na_position="last")
    coords.to_csv(COORDINATE_FILE, index=False)
    return coords


def parse_locations(locations):
    if pd.isna(locations):
        return []
    split_codes = re.split(r"[|,]", str(locations))
    return [code.strip() for code in split_codes if code.strip()]


def build_funding_base_key(code, year):
    if not isinstance(code, str) or not code:
        return code
    if pd.isna(year):
        return code

    yy = int(year) % 100
    year_token = f"{yy:02d}"
    # Remove the trailing two-digit year token while preserving variant suffixes like "a" or "b".
    return re.sub(rf"{year_token}(?=[A-Za-z]?$)", "", code)


def normalize_plan_name(name):
    text = str(name or "").lower()
    text = re.sub(r"\b(19|20)\d{2}\b", " ", text)
    text = re.sub(rf"\b({MONTHS_PATTERN})\b", " ", text)
    text = re.sub(r"\b\d+\b", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _json_number(value):
    if pd.isna(value):
        return None
    return float(value)


def _display_score(value):
    numeric = pd.to_numeric(value, errors="coerce")
    if pd.isna(numeric):
        return None
    return round(float(numeric) * 100.0, 1)


def _display_normalized_category_score(item):
    if not isinstance(item, dict):
        return None

    gap = pd.to_numeric(item.get("gap"), errors="coerce")
    if pd.notna(gap):
        return _display_score(gap)

    category_score = pd.to_numeric(item.get("category_score"), errors="coerce")
    weight = pd.to_numeric(item.get("weight"), errors="coerce")
    if pd.notna(category_score) and pd.notna(weight) and weight > 0:
        return _display_score(category_score / weight)

    return None


def _with_requirement_fallback(requirements, requirements_last_year):
    requirements = pd.to_numeric(requirements, errors="coerce")
    requirements_last_year = pd.to_numeric(requirements_last_year, errors="coerce")
    if isinstance(requirements, pd.Series):
        return requirements.where(requirements.notna(), requirements_last_year)
    return requirements if pd.notna(requirements) else requirements_last_year


def _fit_requirement_bootstrap_adjustments(history):
    valid = history[["benchmark_key", "requirements_last_year_raw", "requirements"]].copy()
    valid["requirements_last_year_raw"] = pd.to_numeric(
        valid["requirements_last_year_raw"], errors="coerce"
    )
    valid["requirements"] = pd.to_numeric(valid["requirements"], errors="coerce")
    valid = valid[
        valid["benchmark_key"].notna()
        & valid["requirements_last_year_raw"].notna()
        & valid["requirements"].notna()
        & (valid["requirements_last_year_raw"] > 0)
        & (valid["requirements"] > 0)
    ]

    if valid.empty:
        return pd.DataFrame(
            columns=[
                "benchmark_key",
                "requirement_bootstrap_avg_delta",
            ]
        )

    adjustments = []
    for benchmark_key, group in valid.groupby("benchmark_key"):
        x = group["requirements_last_year_raw"].astype(float)
        y = group["requirements"].astype(float)
        avg_delta = float((y - x).mean()) if len(group) > 0 else 0.0
        if pd.isna(avg_delta):
            avg_delta = 0.0

        adjustments.append(
            {
                "benchmark_key": benchmark_key,
                "requirement_bootstrap_avg_delta": avg_delta,
            }
        )

    return pd.DataFrame(adjustments)


def build_latest_canonical_key_map(summary):
    if summary.empty:
        return {}

    key_map = {}
    location_col = "primary_location"
    if location_col not in summary.columns and "primary_location_code" in summary.columns:
        location_col = "primary_location_code"

    work_cols = ["code", "year", location_col]
    if "name" in summary.columns:
        work_cols.append("name")

    work = summary[work_cols].copy()
    work = work.rename(columns={location_col: "location_code"})
    if "name" not in work.columns:
        work["name"] = ""
    work = work[
        work["code"].notna() & work["year"].notna() & work["location_code"].notna()
    ]
    if work.empty:
        return {}

    work["base_key"] = work.apply(
        lambda row: build_funding_base_key(row.get("code"), row.get("year")), axis=1
    )
    work["name_norm"] = work["name"].map(normalize_plan_name)

    for country, family in COUNTRY_STITCHED_BASE_KEY_FAMILIES.items():
        family_rows = work[
            (work["location_code"].astype(str).str.upper() == country)
            & (work["base_key"].isin(family))
        ]
        if family_rows.empty:
            continue

        latest_year = family_rows["year"].max()
        latest_rows = family_rows[family_rows["year"] == latest_year]
        latest_keys = sorted(set(latest_rows["base_key"].dropna().tolist()))
        if not latest_keys:
            continue

        canonical_latest = latest_keys[0]
        for base_key in family:
            key_map[(country, base_key)] = canonical_latest

    for rule in GLOBAL_STITCHED_BASE_KEY_RULES:
        family_rows = work[
            work["base_key"].isin(rule["base_keys"])
            & work["name_norm"].isin(rule["name_norms"])
        ]
        if family_rows.empty:
            continue

        latest_year = family_rows["year"].max()
        latest_rows = family_rows[family_rows["year"] == latest_year]
        latest_keys = sorted(set(latest_rows["base_key"].dropna().tolist()))
        if not latest_keys:
            continue

        canonical_latest = latest_keys[0]
        for base_key in rule["base_keys"]:
            key_map[("__GLOBAL__", rule["label"], base_key)] = canonical_latest

    return key_map


def apply_latest_canonical_key(base_key, primary_location, plan_name, canonical_key_map):
    if not isinstance(primary_location, str) or not primary_location:
        location = None
    else:
        location = primary_location.upper()

    name_norm = normalize_plan_name(plan_name)

    if location is not None:
        country_key = canonical_key_map.get((location, base_key))
        if country_key is not None:
            return country_key

    for rule in GLOBAL_STITCHED_BASE_KEY_RULES:
        if name_norm in rule["name_norms"] and base_key in rule["base_keys"]:
            return canonical_key_map.get(("__GLOBAL__", rule["label"], base_key), base_key)

    return base_key


def build_category_scores(category_breakdown):
    if not isinstance(category_breakdown, list) or not category_breakdown:
        return [], None

    valid_categories = []
    total_in_need = 0.0

    for item in category_breakdown:
        if not isinstance(item, dict):
            continue

        category = item.get("category")
        in_need = pd.to_numeric(item.get("in_need"), errors="coerce")
        targeted = pd.to_numeric(item.get("targeted"), errors="coerce")

        if pd.isna(in_need) or in_need <= 0 or pd.isna(targeted):
            continue

        coverage = max(0.0, min(float(targeted) / float(in_need), 1.0))
        gap = 1.0 - coverage
        valid_categories.append(
            {
                "category": category,
                "in_need": float(in_need),
                "targeted": float(targeted),
                "coverage": coverage,
                "gap": gap,
            }
        )
        total_in_need += float(in_need)

    if not valid_categories or total_in_need <= 0:
        return [], None

    weighted_gap_sum = 0.0
    for item in valid_categories:
        weight = item["in_need"] / total_in_need
        item["weight"] = weight
        item["category_score"] = weight * item["gap"]
        weighted_gap_sum += item["category_score"]

    return valid_categories, weighted_gap_sum


def compute_overall_severity_score(row):
    category_score = row.get("category_level_score")
    percent_funded = pd.to_numeric(row.get("percent_funded"), errors="coerce")
    systematic_score = pd.to_numeric(
        row.get("systematic_underfunding_score"), errors="coerce"
    )

    funding_gap = None
    if not pd.isna(percent_funded):
        funding_gap = max(0.0, min(1.0, 1.0 - float(percent_funded) / 100.0))

    components = []
    weights = []

    if category_score is not None and not pd.isna(category_score):
        components.append(float(category_score))
        weights.append(0.5)
    if funding_gap is not None and not pd.isna(funding_gap):
        components.append(float(funding_gap))
        weights.append(0.3)
    if systematic_score is not None and not pd.isna(systematic_score):
        components.append(float(systematic_score))
        weights.append(0.2)

    if not components:
        return None

    total_weight = sum(weights)
    return sum(value * weight for value, weight in zip(components, weights)) / total_weight


def build_historical_benchmark_data(summary):
    canonical_key_map = build_latest_canonical_key_map(summary)
    historical = summary[
        [
            "code",
            "name",
            "year",
            "requirements",
            "requirements_last_year",
            "funding",
            "primary_location",
        ]
    ].copy()
    historical["requirements_effective"] = _with_requirement_fallback(
        historical["requirements"],
        historical["requirements_last_year"],
    )
    historical["benchmark_key"] = historical.apply(
        lambda row: apply_latest_canonical_key(
            build_funding_base_key(row.get("code"), row.get("year")),
            row.get("primary_location"),
            row.get("name"),
            canonical_key_map,
        ),
        axis=1,
    )

    historical = historical.groupby(["benchmark_key", "year"], as_index=False).agg(
        requirements=("requirements_effective", "sum"),
        funding=("funding", "sum"),
    )
    historical["percent_funded"] = (
        100 * historical["funding"] / historical["requirements"]
    )
    historical.loc[historical["requirements"] == 0, "percent_funded"] = None

    yearly_totals = historical.groupby("year", as_index=False).agg(
        total_requirements=("requirements", "sum"),
        total_funding=("funding", "sum"),
    )
    yearly_totals["avg_percent_funded_raw"] = (
        100 * yearly_totals["total_funding"] / yearly_totals["total_requirements"]
    )
    yearly_totals.loc[
        yearly_totals["total_requirements"] == 0, "avg_percent_funded_raw"
    ] = None
    yearly_totals["avg_percent_funded"] = yearly_totals["avg_percent_funded_raw"].round(1)

    historical = historical.merge(
        yearly_totals[["year", "avg_percent_funded_raw", "avg_percent_funded"]],
        how="left",
        on="year",
    )
    return historical


def apply_last_year_requirement_fallback(funding_summary, plans, target_year=2026):
    if funding_summary.empty:
        funding_summary = funding_summary.copy()
        funding_summary["requirements_last_year"] = pd.Series(dtype=float)
        funding_summary["requirements_last_year_raw"] = pd.Series(dtype=float)
        funding_summary["requirement_bootstrap_avg_delta"] = pd.Series(dtype=float)
        return funding_summary

    funding_summary = funding_summary.copy()

    plan_keys = plans[["code", "year", "primary_location", "planVersion"]].copy()
    plan_keys = plan_keys.dropna(subset=["code", "year", "primary_location"])
    plan_keys = plan_keys.drop_duplicates(subset=["code", "year"], keep="first")
    plan_keys = plan_keys.rename(columns={"planVersion": "name"})

    canonical_key_map = build_latest_canonical_key_map(plan_keys)
    funding_summary = funding_summary.merge(
        plan_keys,
        how="left",
        on=["code", "year"],
    )
    funding_summary["benchmark_key"] = funding_summary.apply(
        lambda row: apply_latest_canonical_key(
            build_funding_base_key(row.get("code"), row.get("year")),
            row.get("primary_location"),
            row.get("name"),
            canonical_key_map,
        ),
        axis=1,
    )

    previous_year = funding_summary[
        ["benchmark_key", "year", "requirements", "funding"]
    ].copy()
    previous_year["year"] = previous_year["year"] + 1
    previous_year["requirements_last_year_raw"] = (
        previous_year["requirements"] - previous_year["funding"]
    ).clip(lower=0)
    previous_year = previous_year[
        ["benchmark_key", "year", "requirements_last_year_raw"]
    ]

    funding_summary = funding_summary.merge(
        previous_year,
        how="left",
        on=["benchmark_key", "year"],
    )
    bootstrap_models = _fit_requirement_bootstrap_adjustments(funding_summary)
    funding_summary = funding_summary.merge(
        bootstrap_models,
        how="left",
        on="benchmark_key",
    )
    funding_summary["requirement_bootstrap_avg_delta"] = funding_summary[
        "requirement_bootstrap_avg_delta"
    ].fillna(0.0)
    funding_summary["requirements_last_year"] = (
        funding_summary["requirements_last_year_raw"]
        + funding_summary["requirement_bootstrap_avg_delta"]
    ).clip(lower=0)

    zero_requirement_mask = (
        funding_summary["year"].eq(target_year) & funding_summary["requirements"].eq(0)
    )
    funding_summary.loc[zero_requirement_mask, "requirements"] = pd.NA

    return funding_summary.drop(columns=["primary_location", "name", "benchmark_key"])


def compute_systematic_underfunding_metrics(historical):
    if historical.empty:
        return pd.DataFrame(
            columns=[
                "benchmark_key",
                "systematic_underfunding_score",
                "weighted_avg_underfunding_gap",
                "underfunded_year_share",
                "max_underfunding_gap",
                "historical_years_count",
            ]
        )

    metrics = []
    for benchmark_key, group in historical.groupby("benchmark_key"):
        valid = group[
            group["percent_funded"].notna() & group["avg_percent_funded_raw"].notna()
        ].copy()

        if valid.empty:
            metrics.append(
                {
                    "benchmark_key": benchmark_key,
                    "systematic_underfunding_score": None,
                    "weighted_avg_underfunding_gap": None,
                    "underfunded_year_share": None,
                    "max_underfunding_gap": None,
                    "historical_years_count": 0,
                }
            )
            continue

        valid["gap_vs_benchmark"] = (
            valid["avg_percent_funded_raw"] - valid["percent_funded"]
        )
        valid["underfunding_gap"] = valid["gap_vs_benchmark"].clip(lower=0)

        req = pd.to_numeric(valid["requirements"], errors="coerce").fillna(0.0)
        if req.sum() > 0:
            weights = req / req.sum()
        else:
            weights = pd.Series(
                [1.0 / len(valid)] * len(valid), index=valid.index, dtype=float
            )

        ss_under = float((weights * (valid["underfunding_gap"] ** 2)).sum())
        ss_all = float((weights * (valid["gap_vs_benchmark"] ** 2)).sum())
        eta_sq = ss_under / ss_all if ss_all > 0 else None
        avg_gap = float((weights * valid["underfunding_gap"]).sum())
        underfunded_share = float((valid["gap_vs_benchmark"] > 0).mean())
        max_gap = float(valid["underfunding_gap"].max())

        metrics.append(
            {
                "benchmark_key": benchmark_key,
                "systematic_underfunding_score": eta_sq,
                "weighted_avg_underfunding_gap": avg_gap,
                "underfunded_year_share": underfunded_share,
                "max_underfunding_gap": max_gap,
                "historical_years_count": int(len(valid)),
            }
        )

    return pd.DataFrame(metrics)


def build_systematic_underfunding_json(row):
    return {
        "score": (
            None
            if pd.isna(
                pd.to_numeric(row.get("systematic_underfunding_score"), errors="coerce")
            )
            else float(
                pd.to_numeric(row.get("systematic_underfunding_score"), errors="coerce")
            )
        ),
        "weighted_avg_underfunding_gap": (
            None
            if pd.isna(
                pd.to_numeric(row.get("weighted_avg_underfunding_gap"), errors="coerce")
            )
            else float(
                pd.to_numeric(row.get("weighted_avg_underfunding_gap"), errors="coerce")
            )
        ),
        "underfunded_year_share": (
            None
            if pd.isna(pd.to_numeric(row.get("underfunded_year_share"), errors="coerce"))
            else float(pd.to_numeric(row.get("underfunded_year_share"), errors="coerce"))
        ),
        "max_underfunding_gap": (
            None
            if pd.isna(pd.to_numeric(row.get("max_underfunding_gap"), errors="coerce"))
            else float(pd.to_numeric(row.get("max_underfunding_gap"), errors="coerce"))
        ),
        "historical_years_count": (
            None
            if pd.isna(pd.to_numeric(row.get("historical_years_count"), errors="coerce"))
            else int(pd.to_numeric(row.get("historical_years_count"), errors="coerce"))
        ),
    }


def _combine_category_breakdown(rows):
    combined = {}
    for value in rows:
        if not isinstance(value, list):
            continue
        for item in value:
            if not isinstance(item, dict):
                continue
            category = item.get("category")
            if not category:
                continue
            in_need = pd.to_numeric(item.get("in_need"), errors="coerce")
            targeted = pd.to_numeric(item.get("targeted"), errors="coerce")
            if pd.isna(in_need) and pd.isna(targeted):
                continue

            if category not in combined:
                combined[category] = {"category": category, "in_need": 0.0, "targeted": 0.0}

            if not pd.isna(in_need):
                combined[category]["in_need"] += float(in_need)
            if not pd.isna(targeted):
                combined[category]["targeted"] += float(targeted)

    return list(combined.values())


def _pick_first_dict(series):
    for value in series:
        if isinstance(value, dict):
            return value
    return None


def build_all_years_export(summary):
    records = []
    data = summary.copy()
    data["requirements_effective"] = _with_requirement_fallback(
        data["requirements"],
        data["requirements_last_year"],
    )
    canonical_key_map = build_latest_canonical_key_map(data)
    data["funding_base_key"] = data.apply(
        lambda row: apply_latest_canonical_key(
            build_funding_base_key(row.get("code"), row.get("year")),
            row.get("primary_location_code"),
            row.get("name"),
            canonical_key_map,
        ),
        axis=1,
    )

    yearly_totals = (
        data.groupby("year", dropna=True)
        .agg(
            total_requirements=("requirements_effective", "sum"),
            total_funding=("funding", "sum"),
        )
        .reset_index()
    )
    yearly_totals["avg_percent_funded"] = (
        100 * yearly_totals["total_funding"] / yearly_totals["total_requirements"]
    ).round(1)
    yearly_totals.loc[
        yearly_totals["total_requirements"] == 0, "avg_percent_funded"
    ] = None
    yearly_avg_percent_map = {
        int(row["year"]): _json_number(row["avg_percent_funded"])
        for _, row in yearly_totals.iterrows()
        if pd.notna(row["year"])
    }

    for base_key, group in data.groupby("funding_base_key", dropna=False):
        group = group.sort_values(by="year")
        preferred = group[group["year"] == 2026]

        def _pick_location_field(field_name):
            sources = [preferred, group] if not preferred.empty else [group]
            for source in sources:
                for value in source[field_name].tolist():
                    if isinstance(value, list) and value:
                        cleaned = [item for item in value if item]
                        if cleaned:
                            return list(dict.fromkeys(cleaned))
            return []

        def _pick_scalar_field(field_name):
            sources = [preferred, group] if not preferred.empty else [group]
            for source in sources:
                non_null = source[field_name].dropna()
                if not non_null.empty:
                    return non_null.iloc[0]
            return None

        location_codes = _pick_location_field("location_codes")
        location_names = _pick_location_field("location_names")
        primary_location_code = _pick_scalar_field("primary_location_code")
        primary_location_name = _pick_scalar_field("primary_location_name")
        latitude = _pick_scalar_field("latitude")
        longitude = _pick_scalar_field("longitude")

        systematic_underfunding = _pick_first_dict(group.get("systematic_underfunding", []))

        group_2026 = group[group["year"] == 2026]
        project_metrics_2026 = None
        if not group_2026.empty:
            requirements_2026 = group_2026["requirements"].sum(min_count=1)
            requirements_last_year_2026 = group_2026["requirements_last_year"].sum(
                min_count=1
            )
            requirements_last_year_raw_2026 = group_2026[
                "requirements_last_year_raw"
            ].sum(min_count=1)
            requirement_bootstrap_avg_delta_2026 = group_2026[
                "requirement_bootstrap_avg_delta"
            ].mean()
            effective_requirements_2026 = _with_requirement_fallback(
                requirements_2026,
                requirements_last_year_2026,
            )
            funding_2026 = group_2026["funding"].sum(min_count=1)
            contribution_count_2026 = group_2026["contribution_count"].sum(min_count=1)

            percent_funded_2026 = None
            if (
                pd.notna(effective_requirements_2026)
                and effective_requirements_2026 != 0
                and pd.notna(funding_2026)
            ):
                percent_funded_2026 = round(
                    (funding_2026 / effective_requirements_2026) * 100, 1
                )

            category_breakdown_2026 = _combine_category_breakdown(
                group_2026.get("category_breakdown", pd.Series(dtype=object))
            )
            category_breakdown_scored_2026, category_level_score_2026 = (
                build_category_scores(category_breakdown_2026)
            )

            overall_severity_score_2026 = compute_overall_severity_score(
                {
                    "category_level_score": category_level_score_2026,
                    "percent_funded": percent_funded_2026,
                    "systematic_underfunding_score": (
                        systematic_underfunding.get("score")
                        if isinstance(systematic_underfunding, dict)
                        else None
                    ),
                }
            )

            project_metrics_2026 = {
                "requirements": _json_number(requirements_2026),
                "requirements_last_year": _json_number(requirements_last_year_2026),
                "requirements_last_year_raw": _json_number(
                    requirements_last_year_raw_2026
                ),
                "requirement_bootstrap_avg_delta": _json_number(
                    requirement_bootstrap_avg_delta_2026
                ),
                "funding": _json_number(funding_2026),
                "percent_funded": _json_number(percent_funded_2026),
                "contribution_count": int(contribution_count_2026)
                if pd.notna(contribution_count_2026)
                else None,
                "category_breakdown_scored": [
                    {
                        **item,
                        "category_score": _display_score(item.get("category_score")),
                        "category_score_normalized": _display_normalized_category_score(
                            item
                        ),
                    }
                    for item in category_breakdown_scored_2026
                ],
                "category_level_score": _display_score(category_level_score_2026),
                "overall_severity_score": _display_score(overall_severity_score_2026),
            }

        payload = {
            "funding_base_key": base_key,
            "primary_location_code": primary_location_code,
            "primary_location_name": primary_location_name,
            "location_codes": location_codes,
            "location_names": location_names,
            "latitude": _json_number(latitude),
            "longitude": _json_number(longitude),
            "systematic_underfunding": (
                {
                    **systematic_underfunding,
                    "score": _display_score(systematic_underfunding.get("score")),
                }
                if isinstance(systematic_underfunding, dict)
                else systematic_underfunding
            ),
            "years": {},
        }
        if project_metrics_2026 is not None:
            payload["project_metrics_2026"] = project_metrics_2026

        if not group_2026.empty:
            has_people_data = group_2026[
                [
                    "people_in_need",
                    "people_targeted",
                    "people_affected",
                    "people_reached",
                ]
            ].notna().any().any()
            if has_people_data:
                payload["people_2026"] = {
                    "people_in_need": _json_number(
                        group_2026["people_in_need"].sum(min_count=1)
                    ),
                    "people_targeted": _json_number(
                        group_2026["people_targeted"].sum(min_count=1)
                    ),
                    "people_affected": _json_number(
                        group_2026["people_affected"].sum(min_count=1)
                    ),
                    "people_reached": _json_number(
                        group_2026["people_reached"].sum(min_count=1)
                    ),
                }

        for year, year_group in group.groupby("year", dropna=False):
            year_key = str(int(year)) if pd.notna(year) else "unknown"
            year_requirements = year_group["requirements"].sum(min_count=1)
            year_requirements_last_year = year_group["requirements_last_year"].sum(
                min_count=1
            )
            year_requirements_last_year_raw = year_group[
                "requirements_last_year_raw"
            ].sum(min_count=1)
            year_requirement_bootstrap_avg_delta = year_group[
                "requirement_bootstrap_avg_delta"
            ].mean()
            year_effective_requirements = _with_requirement_fallback(
                year_requirements,
                year_requirements_last_year,
            )
            year_funding = year_group["funding"].sum(min_count=1)
            payload["years"][year_key] = {
                "codes": sorted(
                    [str(code) for code in year_group["code"].dropna().unique().tolist()]
                ),
                "names": sorted(
                    [str(name) for name in year_group["name"].dropna().unique().tolist()]
                ),
                "requirements": _json_number(year_requirements),
                "requirements_last_year": _json_number(year_requirements_last_year),
                "requirements_last_year_raw": _json_number(
                    year_requirements_last_year_raw
                ),
                "requirement_bootstrap_avg_delta": _json_number(
                    year_requirement_bootstrap_avg_delta
                ),
                "funding": _json_number(year_funding),
                "percent_funded": _json_number(
                    round((year_funding / year_effective_requirements) * 100, 1)
                )
                if pd.notna(year_effective_requirements)
                and year_effective_requirements != 0
                and pd.notna(year_funding)
                else None,
                "contribution_count": int(year_group["contribution_count"].sum(min_count=1))
                if pd.notna(year_group["contribution_count"].sum(min_count=1))
                else None,
                "avg_percent_funded": yearly_avg_percent_map.get(int(year))
                if pd.notna(year)
                else None,
            }

        records.append(payload)

    records.sort(
        key=lambda x: (
            x.get("primary_location_name") is None,
            str(x.get("primary_location_name") or ""),
            str(x.get("funding_base_key") or ""),
        )
    )
    return records


def iso3_to_country_name(code):
    if not code:
        return None

    if code in COUNTRY_NAME_OVERRIDES:
        return COUNTRY_NAME_OVERRIDES[code]

    try:
        country = pycountry.countries.get(alpha_3=code)
    except LookupError:
        country = None
    if not country:
        return code

    return getattr(country, "common_name", None) or country.name


def load_plans(year=None):
    plans = pd.read_csv(DATA_DIR / "humanitarian-response-plans.csv", comment="#")
    plans["year"] = pd.to_numeric(plans["years"], errors="coerce")
    if year is not None:
        plans = plans[plans["year"] == year].copy()
    else:
        plans = plans.copy()

    plans["location_codes"] = plans["locations"].apply(parse_locations)
    plans["primary_location"] = plans["location_codes"].apply(
        lambda x: x[0] if x else None
    )
    return plans


def load_requirements_funding(year=None):
    fts = pd.read_csv(DATA_DIR / "fts_requirements_funding_global.csv", comment="#")
    fts["year"] = pd.to_numeric(fts["year"], errors="coerce")
    fts["requirements"] = pd.to_numeric(fts["requirements"], errors="coerce")
    fts["funding"] = pd.to_numeric(fts["funding"], errors="coerce")
    if year is not None:
        return fts[fts["year"] == year].copy()
    return fts.copy()


def load_incoming_funding(year=None):
    funding = pd.read_csv(DATA_DIR / "fts_incoming_funding_global.csv", comment="#")
    funding["year"] = pd.to_numeric(funding["budgetYear"], errors="coerce")
    funding["amountUSD"] = pd.to_numeric(funding["amountUSD"], errors="coerce")
    if year is not None:
        return funding[funding["year"] == year].copy()
    return funding.copy()


def load_severity():
    severity = pd.read_csv(DATA_DIR / "hpc_hno_2026.csv")
    severity["year"] = 2026

    numeric_cols = ["Population", "In Need", "Targeted", "Affected", "Reached"]
    for col in numeric_cols:
        if col in severity.columns:
            severity[col] = pd.to_numeric(severity[col], errors="coerce")

    # Normalize description
    if "Description" in severity.columns:
        severity["desc_norm"] = (
            severity["Description"].astype(str).str.lower().str.strip()
        )
        severity["desc_norm"] = severity["desc_norm"].map(DESCRIPTION_MAP)
    # Keep ALL cluster for totals
    severity_all = severity[severity["Cluster"] == "ALL"].copy()

    # Build per-category breakdown (In Need + Targeted)
    if "Country ISO3" in severity.columns and "desc_norm" in severity.columns:
        severity_mapped = severity[severity["desc_norm"].notna()].copy()
        breakdown = severity_mapped.groupby(
            ["Country ISO3", "desc_norm"], as_index=False
        )[["In Need", "Targeted"]].sum()

        breakdown_records = breakdown.rename(
            columns={
                "desc_norm": "category",
                "In Need": "in_need",
                "Targeted": "targeted",
            }
        )
        breakdown_json = (
            breakdown_records.groupby("Country ISO3", as_index=False)
            .agg(
                category_breakdown=(
                    "category",
                    lambda categories: [
                        {
                            "category": category,
                            "in_need": float(in_need) if pd.notna(in_need) else None,
                            "targeted": float(targeted) if pd.notna(targeted) else None,
                        }
                        for category, in_need, targeted in zip(
                            categories,
                            breakdown_records.loc[categories.index, "in_need"],
                            breakdown_records.loc[categories.index, "targeted"],
                        )
                    ],
                )
            )
        )
        breakdown_json["year"] = 2026
    else:
        breakdown_json = pd.DataFrame(
            columns=["Country ISO3", "category_breakdown", "year"]
        )

    return severity_all, breakdown_json


def build_summary(year=None):
    plans = load_plans(year=year)
    fts = load_requirements_funding(year=year)
    contributions = load_incoming_funding(year=year)
    severity, breakdown_json = load_severity()

    funding_summary = fts.groupby(["code", "year"], as_index=False).agg(
        requirements=("requirements", "sum"), funding=("funding", "sum")
    )
    funding_summary = apply_last_year_requirement_fallback(funding_summary, plans)
    funding_summary["requirements_effective"] = _with_requirement_fallback(
        funding_summary["requirements"],
        funding_summary["requirements_last_year"],
    )
    funding_summary["percent_funded"] = (
        100 * funding_summary["funding"] / funding_summary["requirements_effective"]
    ).round(1)
    funding_summary.loc[
        funding_summary["requirements_effective"].isna()
        | funding_summary["requirements_effective"].eq(0),
        "percent_funded",
    ] = None

    contributions_summary = contributions.groupby(
        ["destPlanCode", "year"], as_index=False
    ).agg(
        total_contributions=("amountUSD", "sum"),
        contribution_count=("amountUSD", "count"),
    )

    plan_summary = (
        plans[
            [
                "code",
                "planVersion",
                "locations",
                "primary_location",
                "location_codes",
                "year",
            ]
        ]
        .drop_duplicates(
            subset=["code", "planVersion", "locations", "primary_location", "year"]
        )
        .rename(columns={"planVersion": "name"})
        .merge(
            funding_summary,
            how="left",
            left_on=["code", "year"],
            right_on=["code", "year"],
        )
        .merge(
            contributions_summary,
            how="left",
            left_on=["code", "year"],
            right_on=["destPlanCode", "year"],
        )
    )

    country_severity = severity.groupby("Country ISO3", as_index=False)[
        ["In Need", "Targeted", "Affected", "Reached"]
    ].sum()
    country_severity["year"] = 2026
    plan_summary = plan_summary.merge(
        country_severity,
        how="left",
        left_on=["primary_location", "year"],
        right_on=["Country ISO3", "year"],
    )

    plan_summary = plan_summary.merge(
        breakdown_json,
        how="left",
        left_on=["primary_location", "year"],
        right_on=["Country ISO3", "year"],
    )

    plan_summary["primary_location_name"] = plan_summary["primary_location"].apply(
        iso3_to_country_name
    )
    plan_summary["location_names"] = plan_summary["location_codes"].apply(
        lambda codes: (
            [iso3_to_country_name(code) for code in codes]
            if isinstance(codes, list)
            else []
        )
    )

    # Add coordinates using the geocoder pipeline cache
    primary_name_lookup = (
        plan_summary[["primary_location", "primary_location_name"]]
        .dropna(subset=["primary_location"])
        .drop_duplicates(subset=["primary_location"])
        .set_index("primary_location")["primary_location_name"]
        .to_dict()
    )
    coordinates = load_coordinates(primary_name_lookup)
    plan_summary = plan_summary.merge(coordinates, how="left", on="primary_location")

    if "category_breakdown" in plan_summary.columns:
        plan_summary["category_breakdown"] = plan_summary["category_breakdown"].apply(
            lambda x: x if isinstance(x, list) else []
        )

    category_score_results = plan_summary["category_breakdown"].apply(
        build_category_scores
    )
    plan_summary["category_breakdown_scored"] = category_score_results.apply(
        lambda x: x[0]
    )
    plan_summary["category_level_score"] = category_score_results.apply(lambda x: x[1])

    historical = build_historical_benchmark_data(plan_summary)
    systematic_metrics = compute_systematic_underfunding_metrics(historical)
    canonical_key_map = build_latest_canonical_key_map(plan_summary)
    plan_summary["benchmark_key"] = plan_summary.apply(
        lambda row: apply_latest_canonical_key(
            build_funding_base_key(row.get("code"), row.get("year")),
            row.get("primary_location"),
            row.get("name"),
            canonical_key_map,
        ),
        axis=1,
    )
    plan_summary = plan_summary.merge(
        systematic_metrics,
        how="left",
        on="benchmark_key",
    )
    plan_summary["systematic_underfunding"] = plan_summary.apply(
        build_systematic_underfunding_json, axis=1
    )

    plan_summary["overall_severity_score"] = None
    severity_mask = plan_summary["year"] == 2026
    plan_summary.loc[severity_mask, "overall_severity_score"] = plan_summary.loc[
        severity_mask
    ].apply(compute_overall_severity_score, axis=1)

    plan_summary = plan_summary.sort_values(
        by=["year", "overall_severity_score", "requirements"],
        ascending=[False, False, False],
    )
    return plan_summary


def print_top_crises(summary, top_n=25, year=None):
    display_columns = [
        "code",
        "name",
        "locations",
        "requirements",
        "funding",
        "percent_funded",
        "category_level_score",
        "overall_severity_score",
        "systematic_underfunding_score",
        "weighted_avg_underfunding_gap",
        "underfunded_year_share",
        "total_contributions",
        "In Need",
        "Targeted",
        "Affected",
        "Reached",
    ]
    display_summary = summary.copy()
    for col in [
        "category_level_score",
        "overall_severity_score",
        "systematic_underfunding_score",
    ]:
        if col in display_summary.columns:
            display_summary[col] = display_summary[col].apply(_display_score)

    if year is None:
        print("Top crisis plans across all years by requirements and funding status:\n")
    else:
        print(f"Top {year} crisis plans by requirements and funding status:\n")
    print(display_summary[display_columns].head(top_n).to_string(index=False))


def main():
    summary = build_summary(year=None)
    print_top_crises(summary, year=None)
    # Normalize every JSON field name to snake_case
    column_rename = {
        "destPlanCode": "dest_plan_code",
        "Country ISO3": "country_iso3",
        "primary_location": "primary_location_code",
        "In Need": "people_in_need",
        "Targeted": "people_targeted",
        "Affected": "people_affected",
        "Reached": "people_reached",
    }
    summary = summary.rename(columns=column_rename)
    summary = summary.drop(columns=["locations", "total_contributions"], errors="ignore")

    json_file = Path(__file__).resolve().parent / "crisis_summary_all_years.json"
    all_years_export = build_all_years_export(summary)
    json_file.write_text(json.dumps(all_years_export, indent=2), encoding="utf-8")
    print(f"\nSaved plan summary to {json_file}")


if __name__ == "__main__":
    main()
