import re
from pathlib import Path

import pandas as pd
from geopy.extra.rate_limiter import RateLimiter
from geopy.geocoders import Nominatim

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
COORDINATE_FILE = DATA_DIR / "country_coordinates.csv"


def geocode_country(name, geocode):
    try:
        location = geocode(name)
        if location:
            return float(location.latitude), float(location.longitude)
    except Exception:
        pass
    return None, None


def load_coordinates(primary_codes):
    if COORDINATE_FILE.exists():
        coords = pd.read_csv(COORDINATE_FILE)
        if "ISO3" in coords.columns:
            coords = coords.rename(columns={"ISO3": "primary_location"})
    else:
        coords = pd.DataFrame(columns=["primary_location", "latitude", "longitude"])

    coords = coords[["primary_location", "latitude", "longitude"]].drop_duplicates()
    missing_codes = [
        code for code in primary_codes if code not in coords["primary_location"].values
    ]

    geolocator = Nominatim(user_agent="UNDatathonGeocoder/1.0")
    geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)

    for code in missing_codes:
        lat, lon = geocode_country(code, geocode)
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
    # Filter to only "ALL" cluster entries
    severity = severity[severity["Cluster"] == "ALL"]
    return severity


def build_summary():
    plans = load_plans()
    fts = load_requirements_funding()
    contributions = load_incoming_funding()
    severity = load_severity()

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

    # Add coordinates using the geocoder pipeline cache
    primary_codes = plan_summary["primary_location"].dropna().unique().tolist()
    coordinates = load_coordinates(primary_codes)
    plan_summary = plan_summary.merge(coordinates, how="left", on="primary_location")

    plan_summary = plan_summary.sort_values(by="requirements", ascending=False)
    return plan_summary


def print_top_crises(summary, top_n=25):
    display_columns = [
        "code",
        "name",
        "locations",
        "requirements",
        "funding",
        "percent_funded",
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
    # Output to JSON instead of CSV
    json_file = (
        Path(__file__).resolve().parent.parent / "data" / "2026_crisis_summary.json"
    )
    summary.to_json(json_file, orient="records", indent=2)
    print(f"\nSaved plan summary to {json_file}")


if __name__ == "__main__":
    main()
