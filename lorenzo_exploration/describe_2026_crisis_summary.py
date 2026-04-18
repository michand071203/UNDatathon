from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
SUMMARY_CSV = BASE_DIR / "2026_crisis_summary.csv"

NUMERIC_COLUMNS = [
    "requirements",
    "funding",
    "percent_funded",
    "total_contributions",
    "contribution_count",
    "In Need",
    "Targeted",
    "Affected",
    "Reached",
]


def load_summary() -> pd.DataFrame:
    if not SUMMARY_CSV.exists():
        raise FileNotFoundError(f"Summary file not found: {SUMMARY_CSV}")
    df = pd.read_csv(SUMMARY_CSV)
    for col in NUMERIC_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def build_statistics(df: pd.DataFrame) -> pd.DataFrame:
    stats = df[NUMERIC_COLUMNS].describe(percentiles=[0.1, 0.25, 0.5, 0.75, 0.9]).T
    stats["missing_values"] = df[NUMERIC_COLUMNS].isna().sum()
    stats["non_missing_count"] = df[NUMERIC_COLUMNS].notna().sum()
    return stats


def build_extra_insights(df: pd.DataFrame) -> pd.DataFrame:
    insights = []

    total_plans = len(df)
    insights.append({"metric": "total_plans", "value": total_plans})

    insights.append(
        {
            "metric": "plans_with_requirements",
            "value": int(df["requirements"].notna().sum()),
        }
    )

    insights.append(
        {
            "metric": "overall_requirements_usd",
            "value": float(df["requirements"].sum(skipna=True)),
        }
    )

    insights.append(
        {
            "metric": "overall_funding_usd",
            "value": float(df["funding"].sum(skipna=True)),
        }
    )

    insights.append(
        {
            "metric": "overall_contributions_usd",
            "value": float(df["total_contributions"].sum(skipna=True)),
        }
    )

    insights.append(
        {
            "metric": "avg_percent_funded",
            "value": float(df["percent_funded"].mean(skipna=True)),
        }
    )

    underfunded = df[df["percent_funded"].notna() & (df["percent_funded"] < 20)]
    insights.append(
        {
            "metric": "plans_less_than_20pct_funded",
            "value": int(len(underfunded)),
        }
    )

    most_severe = df.sort_values("In Need", ascending=False).head(5)
    insights.append(
        {
            "metric": "top_5_in_need_codes",
            "value": ", ".join(most_severe["code"].astype(str).tolist()),
        }
    )

    plans_by_location = (
        df["primary_location"]
        .value_counts(dropna=True)
        .rename_axis("location")
        .reset_index(name="count")
    )
    plans_by_location.to_csv(
        BASE_DIR / "2026_crisis_summary_plans_by_location.csv", index=False
    )

    return pd.DataFrame(insights)


def main():
    df = load_summary()
    stats = build_statistics(df)
    extra = build_extra_insights(df)

    stats_file = BASE_DIR / "2026_crisis_summary_stats.csv"
    extra_file = BASE_DIR / "2026_crisis_summary_insights.csv"

    stats.to_csv(stats_file)
    extra.to_csv(extra_file, index=False)

    print("Descriptive statistics saved to:")
    print(f"  - {stats_file.name}")
    print(f"  - {extra_file.name}")
    print(f"  - 2026_crisis_summary_plans_by_location.csv")
    print("\nNumeric summary:")
    print(stats)


if __name__ == "__main__":
    main()
