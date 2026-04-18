import json
import csv
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
RANKINGS_JSON = DATA_DIR / "2026_crisis_rankings.json"
RANKINGS_CSV = DATA_DIR / "2026_crisis_all_rankings.csv"


def flatten_rankings(rankings_data):
    flattened = []

    for ranking_category, rankings in rankings_data.items():
        for ranking_name, items in rankings.items():
            for rank, item in enumerate(items, 1):
                row = {
                    "ranking_category": ranking_category,
                    "ranking_name": ranking_name,
                    "rank": rank,
                    "code": item.get("code", ""),
                    "name": item.get("name", ""),
                    "primary_location": item.get("primary_location", ""),
                    "requirements": item.get("requirements", ""),
                    "funding": item.get("funding", ""),
                    "funding_gap": item.get("funding_gap", ""),
                    "percent_funded": item.get("percent_funded", ""),
                    "people_in_need": item.get("people_in_need", ""),
                    "people_targeted": item.get("people_targeted", ""),
                    "people_reached": item.get("people_reached", ""),
                    "target_coverage": item.get("target_coverage", ""),
                    "unmet_need_ratio": item.get("unmet_need_ratio", ""),
                    "funding_per_need": item.get("funding_per_need", ""),
                    "funding_per_target": item.get("funding_per_target", ""),
                    "gap_per_person": item.get("gap_per_person", ""),
                    "people_reached_ratio": item.get("people_reached_ratio", ""),
                    "overall_score": item.get("overall_score", ""),
                    "country": item.get("country", ""),
                    "category": item.get("category", ""),
                    "total_requirements": item.get("total_requirements", ""),
                    "total_funding": item.get("total_funding", ""),
                    "total_funding_gap": item.get("total_funding_gap", ""),
                    "total_people_in_need": item.get("total_people_in_need", ""),
                    "total_people_targeted": item.get("total_people_targeted", ""),
                    "total_people_reached": item.get("total_people_reached", ""),
                    "avg_percent_funded": item.get("avg_percent_funded", ""),
                    "total_coverage": item.get("total_coverage", ""),
                    "total_unmet_need_ratio": item.get("total_unmet_need_ratio", ""),
                    "total_funding_per_need": item.get("total_funding_per_need", ""),
                    "total_funding_per_target": item.get(
                        "total_funding_per_target", ""
                    ),
                    "total_gap_per_person": item.get("total_gap_per_person", ""),
                    "total_reached_ratio": item.get("total_reached_ratio", ""),
                    "category_total_people_in_need": item.get(
                        "category_total_people_in_need", ""
                    ),
                    "category_total_people_targeted": item.get(
                        "category_total_people_targeted", ""
                    ),
                    "category_coverage": item.get("category_coverage", ""),
                    "category_gap": item.get("category_gap", ""),
                }
                flattened.append(row)

    return flattened


def main():
    with open(RANKINGS_JSON, "r", encoding="utf-8") as f:
        rankings_data = json.load(f)

    flattened_data = flatten_rankings(rankings_data)

    if flattened_data:
        # Get all possible columns
        all_columns = set()
        for row in flattened_data:
            all_columns.update(row.keys())

        # Sort columns for consistent order
        columns = sorted(all_columns)

        with open(RANKINGS_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            writer.writeheader()
            writer.writerows(flattened_data)

        print(f"Rankings CSV saved to {RANKINGS_CSV}")
        print(f"Total rows: {len(flattened_data)}")
        print(f"Columns: {', '.join(columns)}")
    else:
        print("No data to write")


if __name__ == "__main__":
    main()
