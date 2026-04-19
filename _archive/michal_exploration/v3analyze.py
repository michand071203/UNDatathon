import json
import re
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

HISTORICAL_JSON_CANDIDATE_FILES = [
    DATA_DIR / "crisis_summary_all_years.json",
    DATA_DIR / "all_years_crisis_export.json",
    DATA_DIR / "all_years_crisis_summary.json",
    DATA_DIR / "historical_crisis_summary.json",
    DATA_DIR / "crisis_history.json",
]


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
        country = pycountry.countries.get(alpha_3=code)
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

    coords.to_csv(COORDINATE_FILE, index=False)
    return coords


def parse_locations(locations):
    if pd.isna(locations):
        return []
    split_codes = re.split(r"[|,]", str(locations))
    return [code.strip() for code in split_codes if code.strip()]


def iso3_to_country_name(code):
    if not code:
        return None

    if code in COUNTRY_NAME_OVERRIDES:
        return COUNTRY_NAME_OVERRIDES[code]

    country = pycountry.countries.get(alpha_3=code)
    if not country:
        return code

    return getattr(country, "common_name", None) or country.name


def load_plans():
    plans = pd.read_csv(DATA_DIR / "humanitarian-response-plans.csv", comment="#")
    plans["year"] = pd.to_numeric(plans["years"], errors="coerce")
    plans_2026 = plans[plans["year"] == 2026].copy()
    plans_2026["location_codes"] = plans_2026["locations"].apply(parse_locations)
    plans_2026["primary_location"] = plans_2026["location_codes"].apply(
        lambda x: x[0] if x else None
    )
    return plans_2026


def load_requirements_funding():
    fts = pd.read_csv(DATA_DIR / "fts_requirements_funding_global.csv", comment="#")
    fts["year"] = pd.to_numeric(fts["year"], errors="coerce")
    fts["requirements"] = pd.to_numeric(fts["requirements"], errors="coerce")
    fts["funding"] = pd.to_numeric(fts["funding"], errors="coerce")
    return fts[fts["year"] == 2026].copy()


def load_incoming_funding():
    funding = pd.read_csv(DATA_DIR / "fts_incoming_funding_global.csv", comment="#")
    funding["year"] = pd.to_numeric(funding["budgetYear"], errors="coerce")
    funding["amountUSD"] = pd.to_numeric(funding["amountUSD"], errors="coerce")
    return funding[funding["year"] == 2026].copy()


def load_severity():
    severity = pd.read_csv(DATA_DIR / "hpc_hno_2026.csv")

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

        breakdown_json = (
            breakdown.groupby("Country ISO3")
            .apply(
                lambda g: g[["desc_norm", "In Need", "Targeted"]]
                .rename(
                    columns={
                        "desc_norm": "category",
                        "In Need": "in_need",
                        "Targeted": "targeted",
                    }
                )
                .to_dict("records")
            )
            .reset_index(name="category_breakdown")
        )
    else:
        breakdown_json = pd.DataFrame(columns=["Country ISO3", "category_breakdown"])

    return severity_all, breakdown_json


# --- Category scoring helpers ---
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


# --- Historical funding analysis helpers ---
def _historical_json_path():
    for candidate in HISTORICAL_JSON_CANDIDATE_FILES:
        if candidate.exists():
            return candidate

    dynamic_candidates = sorted(DATA_DIR.glob("*year*.json")) + sorted(
        DATA_DIR.glob("*histor*.json")
    )
    for candidate in dynamic_candidates:
        if candidate.exists() and candidate.name != "2026_crisis_summary.json":
            return candidate
    return None



def load_historical_benchmark_data():
    json_path = _historical_json_path()
    if json_path is None:
        return pd.DataFrame(
            columns=[
                "benchmark_key",
                "year",
                "requirements",
                "funding",
                "percent_funded",
                "avg_percent_funded_raw",
                "avg_percent_funded",
            ]
        )

    with open(json_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    if not isinstance(payload, list) or not payload:
        return pd.DataFrame(
            columns=[
                "benchmark_key",
                "year",
                "requirements",
                "funding",
                "percent_funded",
                "avg_percent_funded_raw",
                "avg_percent_funded",
            ]
        )

    rows = []
    for item in payload:
        if not isinstance(item, dict):
            continue

        base_key = (
            item.get("primary_location_code")
            or item.get("country_iso3")
            or item.get("primary_location")
            or item.get("funding_base_key")
            or item.get("code")
        )

        if not base_key:
            continue

        years_obj = item.get("years")

        if isinstance(years_obj, dict):
            for year_key, year_item in years_obj.items():
                if not isinstance(year_item, dict):
                    continue
                rows.append(
                    {
                        "benchmark_key": base_key,
                        "year": year_key,
                        "requirements": year_item.get("requirements"),
                        "funding": year_item.get("funding"),
                        "percent_funded": year_item.get("percent_funded"),
                        "avg_percent_funded": year_item.get("avg_percent_funded"),
                    }
                )
        elif isinstance(years_obj, list):
            for year_item in years_obj:
                if not isinstance(year_item, dict):
                    continue
                rows.append(
                    {
                        "benchmark_key": base_key,
                        "year": year_item.get("year"),
                        "requirements": year_item.get("requirements"),
                        "funding": year_item.get("funding"),
                        "percent_funded": year_item.get("percent_funded"),
                        "avg_percent_funded": year_item.get("avg_percent_funded"),
                    }
                )
        else:
            rows.append(
                {
                    "benchmark_key": base_key,
                    "year": item.get("year"),
                    "requirements": item.get("requirements"),
                    "funding": item.get("funding"),
                    "percent_funded": item.get("percent_funded"),
                    "avg_percent_funded": item.get("avg_percent_funded"),
                }
            )

    historical = pd.DataFrame(rows)
    if historical.empty:
        return pd.DataFrame(
            columns=[
                "benchmark_key",
                "year",
                "requirements",
                "funding",
                "percent_funded",
                "avg_percent_funded_raw",
                "avg_percent_funded",
            ]
        )

    historical["year"] = pd.to_numeric(historical["year"], errors="coerce")
    historical["requirements"] = pd.to_numeric(
        historical["requirements"], errors="coerce"
    )
    historical["funding"] = pd.to_numeric(historical["funding"], errors="coerce")
    historical["percent_funded"] = pd.to_numeric(
        historical["percent_funded"], errors="coerce"
    )
    historical["avg_percent_funded"] = pd.to_numeric(
        historical.get("avg_percent_funded"), errors="coerce"
    )
    historical = historical.dropna(subset=["benchmark_key", "year"]).copy()

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
    yearly_totals["avg_percent_funded_recomputed"] = yearly_totals[
        "avg_percent_funded_raw"
    ].round(1)

    historical = historical.merge(
        yearly_totals[
            ["year", "avg_percent_funded_raw", "avg_percent_funded_recomputed"]
        ],
        how="left",
        on="year",
    )
    historical["avg_percent_funded"] = historical["avg_percent_funded_raw"].where(
        historical["avg_percent_funded_raw"].notna(),
        historical["avg_percent_funded"],
    )
    return historical



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


# Helper to build systematic_underfunding JSON field for each row
def build_systematic_underfunding_json(row):
    return {
        "score": (
            None
            if pd.isna(pd.to_numeric(row.get("systematic_underfunding_score"), errors="coerce"))
            else float(pd.to_numeric(row.get("systematic_underfunding_score"), errors="coerce"))
        ),
        "weighted_avg_underfunding_gap": (
            None
            if pd.isna(pd.to_numeric(row.get("weighted_avg_underfunding_gap"), errors="coerce"))
            else float(pd.to_numeric(row.get("weighted_avg_underfunding_gap"), errors="coerce"))
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


def build_summary():
    plans = load_plans()
    fts = load_requirements_funding()
    contributions = load_incoming_funding()
    severity, breakdown_json = load_severity()
    historical = load_historical_benchmark_data()
    systematic_metrics = compute_systematic_underfunding_metrics(historical)

    funding_summary = fts.groupby("code", as_index=False).agg(
        requirements=("requirements", "sum"), funding=("funding", "sum")
    )
    funding_summary["percent_funded"] = (
        100 * funding_summary["funding"] / funding_summary["requirements"]
    ).round(1)
    funding_summary.loc[funding_summary["requirements"] == 0, "percent_funded"] = None

    contributions_summary = contributions.groupby("destPlanCode", as_index=False).agg(
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
        .drop_duplicates(subset=["code"])
        .rename(columns={"planVersion": "name"})
        .merge(funding_summary, how="left", left_on="code", right_on="code")
        .merge(
            contributions_summary, how="left", left_on="code", right_on="destPlanCode"
        )
    )

    country_severity = severity.groupby("Country ISO3", as_index=False)[
        ["In Need", "Targeted", "Affected", "Reached"]
    ].sum()
    plan_summary = plan_summary.merge(
        country_severity,
        how="left",
        left_on="primary_location",
        right_on="Country ISO3",
    )

    plan_summary = plan_summary.merge(
        breakdown_json,
        how="left",
        left_on="primary_location",
        right_on="Country ISO3",
    )
    plan_summary["benchmark_key"] = plan_summary["primary_location"]
    plan_summary = plan_summary.merge(
        systematic_metrics,
        how="left",
        on="benchmark_key",
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
    plan_summary["overall_severity_score"] = plan_summary.apply(
        compute_overall_severity_score, axis=1
    )

    plan_summary = plan_summary.sort_values(
        by=["overall_severity_score", "requirements"], ascending=[False, False]
    )
    return plan_summary


def print_top_crises(summary, top_n=25):
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
    print("Top 2026 crisis plans by requirements and funding status:\n")
    print(summary[display_columns].head(top_n).to_string(index=False))


def main():
    summary = build_summary()
    print_top_crises(summary)
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
    summary["systematic_underfunding"] = summary.apply(
        build_systematic_underfunding_json, axis=1
    )
    summary = summary.drop(
        columns=[
            "locations",
            "total_contributions",
            "systematic_underfunding_score",
            "weighted_avg_underfunding_gap",
            "underfunded_year_share",
            "max_underfunding_gap",
            "historical_years_count",
        ],
        errors="ignore",
    )

    json_file = (
        Path(__file__).resolve().parent.parent / "data" / "2026_crisis_summary.json"
    )
    summary.to_json(json_file, orient="records", indent=2)
    print(f"\nSaved plan summary to {json_file}")


if __name__ == "__main__":
    main()
