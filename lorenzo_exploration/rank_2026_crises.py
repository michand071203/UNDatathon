import json
import pandas as pd
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
INPUT_FILE = DATA_DIR / "2026_crisis_summary.json"
OUTPUT_FILE = DATA_DIR / "2026_crisis_rankings.json"


def load_data():
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    df = pd.DataFrame(data)
    if "primary_location" not in df.columns and "primary_location_code" in df.columns:
        df["primary_location"] = df["primary_location_code"]
    return df


def build_category_people_in_need_rankings(df):
    if "category_breakdown" not in df.columns:
        return []

    rows = []
    for breakdown in df["category_breakdown"].dropna():
        if not isinstance(breakdown, list):
            continue
        for entry in breakdown:
            if not isinstance(entry, dict):
                continue
            category = entry.get("category")
            in_need = entry.get("in_need")
            targeted = entry.get("targeted")
            if category and in_need is not None:
                rows.append(
                    {
                        "category": category,
                        "people_in_need": float(in_need),
                        "people_targeted": (
                            float(targeted) if targeted is not None else 0.0
                        ),
                    }
                )

    if not rows:
        return {
            "by_people_in_need": [],
            "by_category_coverage": [],
            "by_category_gap": [],
        }

    cat_df = pd.DataFrame(rows)
    cat_agg = cat_df.groupby("category", as_index=False).agg(
        {"people_in_need": "sum", "people_targeted": "sum"}
    )
    cat_agg["coverage_ratio"] = cat_agg["people_targeted"] / cat_agg["people_in_need"]
    cat_agg["unmet_need"] = cat_agg["people_in_need"] - cat_agg["people_targeted"]
    cat_agg["unmet_need_ratio"] = cat_agg["unmet_need"] / cat_agg["people_in_need"]
    cat_agg.loc[
        cat_agg["people_in_need"] == 0,
        [
            "coverage_ratio",
            "unmet_need_ratio",
        ],
    ] = None

    return {
        "by_people_in_need": cat_agg.sort_values("people_in_need", ascending=False)[
            ["category", "people_in_need", "people_targeted"]
        ].to_dict("records"),
        "by_category_coverage": cat_agg.sort_values(
            "coverage_ratio", ascending=False, na_position="last"
        )[["category", "people_in_need", "people_targeted", "coverage_ratio"]].to_dict(
            "records"
        ),
        "by_category_gap": cat_agg.sort_values(
            "unmet_need_ratio", ascending=False, na_position="last"
        )[
            ["category", "people_in_need", "people_targeted", "unmet_need_ratio"]
        ].to_dict(
            "records"
        ),
    }


def compute_rankings(df):
    # Compute gap for each plan
    df["funding_gap"] = df["requirements"] - df["funding"]

    # Compute relative metrics
    df["coverage_ratio"] = df["people_targeted"] / df["people_in_need"]
    df["unmet_need_ratio"] = (df["people_in_need"] - df["people_targeted"]) / df[
        "people_in_need"
    ]
    df["funding_per_need"] = df["funding"] / df["people_in_need"]
    df["funding_per_target"] = df["funding"] / df["people_targeted"]
    df["gap_per_person"] = df["funding_gap"] / df["people_in_need"]
    df["reached_ratio"] = df["people_reached"] / df["people_in_need"]

    df.loc[
        df["people_in_need"] == 0,
        [
            "coverage_ratio",
            "unmet_need_ratio",
            "funding_per_need",
            "gap_per_person",
            "reached_ratio",
        ],
    ] = None
    df.loc[df["people_targeted"] == 0, "funding_per_target"] = None

    # Add an overall rank score from each plan ranking category
    df["rank_funding_gap"] = df["funding_gap"].rank(method="dense", ascending=False)
    df["rank_requirements"] = df["requirements"].rank(method="dense", ascending=False)
    df["rank_funding"] = df["funding"].rank(method="dense", ascending=False)
    df["rank_percent_funded"] = df["percent_funded"].rank(
        method="dense", ascending=True, na_option="bottom"
    )
    df["rank_people_in_need"] = df["people_in_need"].rank(
        method="dense", ascending=False, na_option="bottom"
    )
    df["rank_coverage_ratio"] = df["coverage_ratio"].rank(
        method="dense", ascending=False, na_option="bottom"
    )
    df["rank_unmet_need_ratio"] = df["unmet_need_ratio"].rank(
        method="dense", ascending=False, na_option="bottom"
    )
    df["rank_funding_per_need"] = df["funding_per_need"].rank(
        method="dense", ascending=False, na_option="bottom"
    )
    df["rank_funding_per_target"] = df["funding_per_target"].rank(
        method="dense", ascending=False, na_option="bottom"
    )
    df["rank_gap_per_person"] = df["gap_per_person"].rank(
        method="dense", ascending=False, na_option="bottom"
    )
    df["rank_reached_ratio"] = df["reached_ratio"].rank(
        method="dense", ascending=False, na_option="bottom"
    )
    df["overall_rank_score"] = (
        df[
            [
                "rank_funding_gap",
                "rank_requirements",
                "rank_funding",
                "rank_percent_funded",
                "rank_people_in_need",
                "rank_coverage_ratio",
                "rank_unmet_need_ratio",
                "rank_funding_per_need",
                "rank_funding_per_target",
                "rank_gap_per_person",
                "rank_reached_ratio",
            ]
        ]
        .sum(axis=1)
        .astype(int)
    )
    df["overall_rank"] = df["overall_rank_score"].rank(method="dense", ascending=True)

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
        "by_target_coverage": df.sort_values(
            "coverage_ratio", ascending=False, na_position="last"
        )[
            [
                "code",
                "name",
                "primary_location",
                "people_in_need",
                "people_targeted",
                "coverage_ratio",
            ]
        ].to_dict(
            "records"
        ),
        "by_unmet_need_ratio": df.sort_values(
            "unmet_need_ratio", ascending=False, na_position="last"
        )[
            [
                "code",
                "name",
                "primary_location",
                "people_in_need",
                "people_targeted",
                "unmet_need_ratio",
            ]
        ].to_dict(
            "records"
        ),
        "by_funding_per_need": df.sort_values(
            "funding_per_need", ascending=False, na_position="last"
        )[
            [
                "code",
                "name",
                "primary_location",
                "people_in_need",
                "funding",
                "funding_per_need",
            ]
        ].to_dict(
            "records"
        ),
        "by_funding_per_target": df.sort_values(
            "funding_per_target", ascending=False, na_position="last"
        )[
            [
                "code",
                "name",
                "primary_location",
                "people_targeted",
                "funding",
                "funding_per_target",
            ]
        ].to_dict(
            "records"
        ),
        "by_gap_per_person": df.sort_values(
            "gap_per_person", ascending=False, na_position="last"
        )[
            [
                "code",
                "name",
                "primary_location",
                "people_in_need",
                "funding_gap",
                "gap_per_person",
            ]
        ].to_dict(
            "records"
        ),
        "by_people_reached_ratio": df.sort_values(
            "reached_ratio", ascending=False, na_position="last"
        )[
            [
                "code",
                "name",
                "primary_location",
                "people_reached",
                "people_in_need",
                "reached_ratio",
            ]
        ].to_dict(
            "records"
        ),
        "overall": df.sort_values("overall_rank_score", ascending=True)[
            [
                "code",
                "name",
                "primary_location",
                "requirements",
                "funding",
                "funding_gap",
                "percent_funded",
                "people_in_need",
                "people_targeted",
                "coverage_ratio",
                "unmet_need_ratio",
                "funding_per_need",
                "funding_per_target",
                "gap_per_person",
                "reached_ratio",
                "rank_funding_gap",
                "rank_requirements",
                "rank_funding",
                "rank_percent_funded",
                "rank_people_in_need",
                "rank_coverage_ratio",
                "rank_unmet_need_ratio",
                "rank_funding_per_need",
                "rank_funding_per_target",
                "rank_gap_per_person",
                "rank_reached_ratio",
                "overall_rank_score",
                "overall_rank",
            ]
        ].to_dict("records"),
    }

    # Aggregate by country (primary_location)
    agg_columns = {
        "requirements": "sum",
        "funding": "sum",
        "funding_gap": "sum",
        "people_in_need": "sum",
        "people_targeted": "sum",
        "people_affected": "sum",
        "people_reached": "sum",
    }
    if "total_contributions" in df.columns:
        agg_columns["total_contributions"] = "sum"
    if "contribution_count" in df.columns:
        agg_columns["contribution_count"] = "sum"

    country_agg = df.groupby("primary_location").agg(agg_columns).reset_index()

    country_agg["percent_funded"] = (
        country_agg["funding"] / country_agg["requirements"] * 100
    ).round(1)
    country_agg.loc[country_agg["requirements"] == 0, "percent_funded"] = None
    country_agg["coverage_ratio"] = (
        country_agg["people_targeted"] / country_agg["people_in_need"]
    )
    country_agg["unmet_need_ratio"] = (
        country_agg["people_in_need"] - country_agg["people_targeted"]
    ) / country_agg["people_in_need"]
    country_agg["funding_per_need"] = (
        country_agg["funding"] / country_agg["people_in_need"]
    )
    country_agg["funding_per_target"] = (
        country_agg["funding"] / country_agg["people_targeted"]
    )
    country_agg["gap_per_person"] = (
        country_agg["funding_gap"] / country_agg["people_in_need"]
    )
    country_agg["reached_ratio"] = (
        country_agg["people_reached"] / country_agg["people_in_need"]
    )

    country_agg.loc[
        country_agg["people_in_need"] == 0,
        [
            "coverage_ratio",
            "unmet_need_ratio",
            "funding_per_need",
            "gap_per_person",
            "reached_ratio",
        ],
    ] = None
    country_agg.loc[country_agg["people_targeted"] == 0, "funding_per_target"] = None

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
        "by_coverage": country_agg.sort_values(
            "coverage_ratio", ascending=False, na_position="last"
        )[
            [
                "primary_location",
                "people_in_need",
                "people_targeted",
                "coverage_ratio",
            ]
        ].to_dict(
            "records"
        ),
        "by_unmet_need_ratio": country_agg.sort_values(
            "unmet_need_ratio", ascending=False, na_position="last"
        )[
            [
                "primary_location",
                "people_in_need",
                "people_targeted",
                "unmet_need_ratio",
            ]
        ].to_dict(
            "records"
        ),
        "by_funding_per_need": country_agg.sort_values(
            "funding_per_need", ascending=False, na_position="last"
        )[
            [
                "primary_location",
                "people_in_need",
                "funding",
                "funding_per_need",
            ]
        ].to_dict(
            "records"
        ),
        "by_funding_per_target": country_agg.sort_values(
            "funding_per_target", ascending=False, na_position="last"
        )[
            [
                "primary_location",
                "people_targeted",
                "funding",
                "funding_per_target",
            ]
        ].to_dict(
            "records"
        ),
        "by_gap_per_person": country_agg.sort_values(
            "gap_per_person", ascending=False, na_position="last"
        )[
            [
                "primary_location",
                "people_in_need",
                "funding_gap",
                "gap_per_person",
            ]
        ].to_dict(
            "records"
        ),
        "by_reached_ratio": country_agg.sort_values(
            "reached_ratio", ascending=False, na_position="last"
        )[
            [
                "primary_location",
                "people_reached",
                "people_in_need",
                "reached_ratio",
            ]
        ].to_dict(
            "records"
        ),
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
        "by_coverage": country_agg.sort_values(
            "coverage_ratio", ascending=False, na_position="last"
        )[
            [
                "primary_location",
                "people_in_need",
                "people_targeted",
                "coverage_ratio",
            ]
        ].to_dict(
            "records"
        ),
        "by_unmet_need_ratio": country_agg.sort_values(
            "unmet_need_ratio", ascending=False, na_position="last"
        )[
            [
                "primary_location",
                "people_in_need",
                "people_targeted",
                "unmet_need_ratio",
            ]
        ].to_dict(
            "records"
        ),
        "by_funding_per_need": country_agg.sort_values(
            "funding_per_need", ascending=False, na_position="last"
        )[
            [
                "primary_location",
                "people_in_need",
                "funding",
                "funding_per_need",
            ]
        ].to_dict(
            "records"
        ),
        "by_funding_per_target": country_agg.sort_values(
            "funding_per_target", ascending=False, na_position="last"
        )[
            [
                "primary_location",
                "people_targeted",
                "funding",
                "funding_per_target",
            ]
        ].to_dict(
            "records"
        ),
        "by_gap_per_person": country_agg.sort_values(
            "gap_per_person", ascending=False, na_position="last"
        )[
            [
                "primary_location",
                "people_in_need",
                "funding_gap",
                "gap_per_person",
            ]
        ].to_dict(
            "records"
        ),
        "by_reached_ratio": country_agg.sort_values(
            "reached_ratio", ascending=False, na_position="last"
        )[
            [
                "primary_location",
                "people_reached",
                "people_in_need",
                "reached_ratio",
            ]
        ].to_dict(
            "records"
        ),
    }

    category_rankings = build_category_people_in_need_rankings(df)

    return {
        "plan_rankings": plan_rankings,
        "country_rankings": country_rankings,
        "category_rankings": category_rankings,
    }


def main():
    df = load_data()
    rankings = compute_rankings(df)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(rankings, f, indent=2, ensure_ascii=False)

    ranking_names = []
    for section, section_rankings in rankings.items():
        if isinstance(section_rankings, dict):
            for ranking_name in section_rankings.keys():
                ranking_names.append(f"{section}.{ranking_name}")

    ranking_names_file = DATA_DIR / "2026_crisis_ranking_names.json"
    with open(ranking_names_file, "w", encoding="utf-8") as f:
        json.dump(ranking_names, f, indent=2, ensure_ascii=False)

    print(f"Rankings saved to {OUTPUT_FILE}")
    print(f"Ranking names saved to {ranking_names_file}")


if __name__ == "__main__":
    main()
