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


def _json_number(value):
    if pd.isna(value):
        return None
    return float(value)


def build_all_years_export(summary):
    records = []
    data = summary.copy()
    data["funding_base_key"] = data.apply(
        lambda row: build_funding_base_key(row.get("code"), row.get("year")), axis=1
    )

    yearly_totals = (
        data.groupby("year", dropna=True)
        .agg(
            total_requirements=("requirements", "sum"),
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

        payload = {
            "funding_base_key": base_key,
            "primary_location_code": primary_location_code,
            "primary_location_name": primary_location_name,
            "location_codes": location_codes,
            "location_names": location_names,
            "latitude": _json_number(latitude),
            "longitude": _json_number(longitude),
            "years": {},
        }

        group_2026 = group[group["year"] == 2026]
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
            year_funding = year_group["funding"].sum(min_count=1)
            payload["years"][year_key] = {
                "codes": sorted(
                    [str(code) for code in year_group["code"].dropna().unique().tolist()]
                ),
                "names": sorted(
                    [str(name) for name in year_group["name"].dropna().unique().tolist()]
                ),
                "requirements": _json_number(year_requirements),
                "funding": _json_number(year_funding),
                "percent_funded": _json_number(
                    round((year_funding / year_requirements) * 100, 1)
                )
                if pd.notna(year_requirements)
                and year_requirements != 0
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
    funding_summary["percent_funded"] = (
        100 * funding_summary["funding"] / funding_summary["requirements"]
    ).round(1)
    funding_summary.loc[funding_summary["requirements"] == 0, "percent_funded"] = None

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

    plan_summary = plan_summary.sort_values(by=["year", "requirements"], ascending=False)
    return plan_summary


def print_top_crises(summary, top_n=25, year=None):
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
    if year is None:
        print("Top crisis plans across all years by requirements and funding status:\n")
    else:
        print(f"Top {year} crisis plans by requirements and funding status:\n")
    print(summary[display_columns].head(top_n).to_string(index=False))


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
    summary = summary.drop(
        columns=["locations", "total_contributions"], errors="ignore"
    )

    json_file = Path(__file__).resolve().parent / "crisis_summary_all_years.json"
    all_years_export = build_all_years_export(summary)
    json_file.write_text(json.dumps(all_years_export, indent=2), encoding="utf-8")
    print(f"\nSaved plan summary to {json_file}")


if __name__ == "__main__":
    main()
