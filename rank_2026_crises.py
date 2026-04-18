import json
import pandas as pd
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
INPUT_FILE = DATA_DIR / "2026_crisis_summary.json"
OUTPUT_FILE = DATA_DIR / "2026_crisis_rankings.json"


def load_data():
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return pd.DataFrame(data)


def compute_rankings(df):
    # Compute gap for each plan
    df["funding_gap"] = df["requirements"] - df["funding"]

    # Rankings for plans (projects)
    plan_rankings = {
        "by_funding_gap": df.sort_values("funding_gap", ascending=False)[
            [
                "code",
                "name",
                "primary_location",
                "requirements",
                "funding",
                "funding_gap",
                "percent_funded",
            ]
        ].to_dict("records"),
        "by_requirements": df.sort_values("requirements", ascending=False)[
            [
                "code",
                "name",
                "primary_location",
                "requirements",
                "funding",
                "funding_gap",
                "percent_funded",
            ]
        ].to_dict("records"),
        "by_funding": df.sort_values("funding", ascending=False)[
            [
                "code",
                "name",
                "primary_location",
                "requirements",
                "funding",
                "funding_gap",
                "percent_funded",
            ]
        ].to_dict("records"),
        "by_percent_funded": df.sort_values("percent_funded", ascending=True)[
            [
                "code",
                "name",
                "primary_location",
                "requirements",
                "funding",
                "funding_gap",
                "percent_funded",
            ]
        ].to_dict("records"),
        "by_people_in_need": df.sort_values(
            "people_in_need", ascending=False, na_position="last"
        )[
            [
                "code",
                "name",
                "primary_location",
                "people_in_need",
                "people_targeted",
                "people_affected",
                "people_reached",
            ]
        ].to_dict(
            "records"
        ),
    }

    # Aggregate by country (primary_location)
    country_agg = (
        df.groupby("primary_location")
        .agg(
            {
                "requirements": "sum",
                "funding": "sum",
                "funding_gap": "sum",
                "people_in_need": "sum",
                "people_targeted": "sum",
                "people_affected": "sum",
                "people_reached": "sum",
                "total_contributions": "sum",
                "contribution_count": "sum",
            }
        )
        .reset_index()
    )

    country_agg["percent_funded"] = (
        country_agg["funding"] / country_agg["requirements"] * 100
    ).round(1)
    country_agg.loc[country_agg["requirements"] == 0, "percent_funded"] = None

    country_rankings = {
        "by_funding_gap": country_agg.sort_values("funding_gap", ascending=False)[
            [
                "primary_location",
                "requirements",
                "funding",
                "funding_gap",
                "percent_funded",
            ]
        ].to_dict("records"),
        "by_requirements": country_agg.sort_values("requirements", ascending=False)[
            [
                "primary_location",
                "requirements",
                "funding",
                "funding_gap",
                "percent_funded",
            ]
        ].to_dict("records"),
        "by_funding": country_agg.sort_values("funding", ascending=False)[
            [
                "primary_location",
                "requirements",
                "funding",
                "funding_gap",
                "percent_funded",
            ]
        ].to_dict("records"),
        "by_percent_funded": country_agg.sort_values(
            "percent_funded", ascending=True, na_position="last"
        )[
            [
                "primary_location",
                "requirements",
                "funding",
                "funding_gap",
                "percent_funded",
            ]
        ].to_dict(
            "records"
        ),
        "by_people_in_need": country_agg.sort_values("people_in_need", ascending=False)[
            [
                "primary_location",
                "people_in_need",
                "people_targeted",
                "people_affected",
                "people_reached",
            ]
        ].to_dict("records"),
    }

    return {"plan_rankings": plan_rankings, "country_rankings": country_rankings}


def main():
    df = load_data()
    rankings = compute_rankings(df)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(rankings, f, indent=2, ensure_ascii=False)
    print(f"Rankings saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
