import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
NAMES_FILE = DATA_DIR / "2026_crisis_ranking_names.json"
TABLE_FILE = DATA_DIR / "2026_crisis_rankings_table.md"


def get_formula(ranking_name):
    formulas = {
        # Plan rankings
        "plan_rankings.by_funding_gap": "requirements - funding",
        "plan_rankings.by_requirements": "requirements",
        "plan_rankings.by_funding": "funding",
        "plan_rankings.by_percent_funded": "percent_funded",
        "plan_rankings.by_people_in_need": "people_in_need",
        "plan_rankings.by_target_coverage": "people_targeted / people_in_need",
        "plan_rankings.by_unmet_need_ratio": "(people_in_need - people_targeted) / people_in_need",
        "plan_rankings.by_funding_per_need": "funding / people_in_need",
        "plan_rankings.by_funding_per_target": "funding / people_targeted",
        "plan_rankings.by_gap_per_person": "funding_gap / people_in_need",
        "plan_rankings.by_people_reached_ratio": "people_reached / people_in_need",
        "plan_rankings.overall": "sum of all individual rank positions",
        # Country rankings
        "country_rankings.by_funding_gap": "sum(requirements - funding) by country",
        "country_rankings.by_requirements": "sum(requirements) by country",
        "country_rankings.by_funding": "sum(funding) by country",
        "country_rankings.by_percent_funded": "funding / requirements * 100 by country",
        "country_rankings.by_people_in_need": "sum(people_in_need) by country",
        "country_rankings.by_coverage": "sum(people_targeted) / sum(people_in_need) by country",
        "country_rankings.by_unmet_need_ratio": "(sum(people_in_need) - sum(people_targeted)) / sum(people_in_need) by country",
        "country_rankings.by_funding_per_need": "sum(funding) / sum(people_in_need) by country",
        "country_rankings.by_funding_per_target": "sum(funding) / sum(people_targeted) by country",
        "country_rankings.by_gap_per_person": "sum(funding_gap) / sum(people_in_need) by country",
        "country_rankings.by_reached_ratio": "sum(people_reached) / sum(people_in_need) by country",
        # Category rankings
        "category_rankings.by_people_in_need": "sum(people_in_need) by category",
        "category_rankings.by_category_coverage": "sum(people_targeted) / sum(people_in_need) by category",
        "category_rankings.by_category_gap": "(sum(people_in_need) - sum(people_targeted)) / sum(people_in_need) by category",
    }
    return formulas.get(ranking_name, "Unknown")


def get_sort_direction(ranking_name):
    # Ascending (lowest first) for metrics where lower is better
    if (
        "percent_funded" in ranking_name
        or "gap_per_person" in ranking_name
        or "unmet_need_ratio" in ranking_name
        or "category_gap" in ranking_name
    ):
        return "ascending (lowest first)"
    # Descending (highest first) for most metrics
    elif (
        "funding_gap" in ranking_name
        or "requirements" in ranking_name
        or "funding" in ranking_name
        or "people_in_need" in ranking_name
        or "target_coverage" in ranking_name
        or "coverage" in ranking_name
        or "funding_per_need" in ranking_name
        or "funding_per_target" in ranking_name
        or "reached_ratio" in ranking_name
        or "people_reached_ratio" in ranking_name
        or "category_coverage" in ranking_name
    ):
        return "descending (highest first)"
    elif "overall" in ranking_name:
        return "ascending (best combined score first)"
    else:
        return "descending (highest first)"


def get_level(ranking_name):
    if "plan_rankings" in ranking_name:
        return "Plan"
    elif "country_rankings" in ranking_name:
        return "Country"
    elif "category_rankings" in ranking_name:
        return "Category"
    return "Unknown"


def main():
    with open(NAMES_FILE, "r", encoding="utf-8") as f:
        ranking_names = json.load(f)

    table_lines = [
        "# 2026 Crisis Rankings Table",
        "",
        "| Ranking Name | Level | Formula | Sort Direction |",
        "|-------------|-------|---------|---------------|",
    ]

    for name in ranking_names:
        formula = get_formula(name)
        level = get_level(name)
        sort_dir = get_sort_direction(name)
        table_lines.append(f"| {name} | {level} | {formula} | {sort_dir} |")

    table_content = "\n".join(table_lines)

    with open(TABLE_FILE, "w", encoding="utf-8") as f:
        f.write(table_content)

    print(f"Rankings table saved to {TABLE_FILE}")


if __name__ == "__main__":
    main()
