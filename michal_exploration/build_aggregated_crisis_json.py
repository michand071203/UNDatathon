import csv
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_JSON = BASE_DIR / "aggregated_crisis_data.json"
REPORT_JSON = BASE_DIR / "aggregation_report.json"
SCOPE_YEAR = 2026


HNO_FILE = DATA_DIR / "hpc_hno_2026.csv"
COD_ADMIN0_FILE = DATA_DIR / "cod_population_admin0.csv"
COD_ADMIN1_FILE = DATA_DIR / "cod_population_admin1.csv"
HRP_FILE = DATA_DIR / "humanitarian-response-plans.csv"
FTS_PLAN_FILE = DATA_DIR / "fts_requirements_funding_global.csv"
FTS_CLUSTER_FILE = DATA_DIR / "fts_requirements_funding_cluster_global.csv"
FTS_GLOBAL_CLUSTER_FILE = DATA_DIR / "fts_requirements_funding_globalcluster_global.csv"
FTS_INCOMING_FILE = DATA_DIR / "fts_incoming_funding_global.csv"
FTS_OUTGOING_FILE = DATA_DIR / "fts_outgoing_funding_global.csv"
FTS_INTERNAL_FILE = DATA_DIR / "fts_internal_funding_global.csv"
CBPF_ALLOCATIONS_FILE = DATA_DIR / "Allocations__20260418_103231_UTC.csv"
CBPF_CONTRIBUTIONS_FILE = DATA_DIR / "Contributions__20260418_103231_UTC.csv"


COUNTRY_NAME_FALLBACKS = {
    "CAF": "Central African Republic",
    "MMR": "Myanmar",
    "SYR": "Syrian Arab Republic",
    "UKR": "Ukraine",
    "YEM": "Yemen",
}


PRIMARY_PLAN_TYPE_PRIORITY = {
    "Humanitarian needs and response plan": 0,
    "Flash appeal": 1,
    "Regional response plan": 2,
    "": 3,
}


def read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def clean_string(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def parse_int(value: Any) -> Optional[int]:
    text = clean_string(value)
    if text is None:
        return None
    try:
        return int(float(text.replace(",", "")))
    except ValueError:
        return None


def parse_float(value: Any) -> Optional[float]:
    text = clean_string(value)
    if text is None:
        return None
    try:
        return float(text.replace(",", ""))
    except ValueError:
        return None


def parse_locations(value: Any) -> List[str]:
    text = clean_string(value)
    if text is None:
        return []
    parts = re.split(r"[|,]", text)
    return [part.strip() for part in parts if part.strip()]


def sort_key_none_last(value: Any) -> Any:
    return (value is None, value)


def choose_first_non_null(values: Iterable[Optional[str]]) -> Optional[str]:
    for value in values:
        if value:
            return value
    return None


def load_hno_data() -> Dict[str, Dict[str, Any]]:
    rows = read_csv(HNO_FILE)
    by_country: Dict[str, Dict[str, Any]] = {}

    for row in rows:
        iso3 = clean_string(row.get("Country ISO3"))
        if iso3 is None:
            continue

        country_record = by_country.setdefault(
            iso3,
            {
                "iso3": iso3,
                "all_row": None,
                "sector_rows": [],
            },
        )

        entry = {
            "cluster_code": clean_string(row.get("Cluster")),
            "description": clean_string(row.get("Description")),
            "category": clean_string(row.get("Category")),
            "population": parse_int(row.get("Population")),
            "people_in_need": parse_int(row.get("In Need")),
            "targeted": parse_int(row.get("Targeted")),
            "affected": parse_int(row.get("Affected")),
            "reached": parse_int(row.get("Reached")),
            "info": clean_string(row.get("Info")),
        }

        if entry["cluster_code"] == "ALL":
            country_record["all_row"] = entry
        else:
            country_record["sector_rows"].append(entry)

    return by_country


def load_cod_reference() -> Dict[str, Dict[str, Any]]:
    admin0_rows = read_csv(COD_ADMIN0_FILE)
    admin1_rows = read_csv(COD_ADMIN1_FILE)

    reference: Dict[str, Dict[str, Any]] = {}
    admin0_by_iso: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    admin1_by_iso: Dict[str, List[Dict[str, str]]] = defaultdict(list)

    for row in admin0_rows:
        iso3 = clean_string(row.get("ISO3"))
        if iso3:
            admin0_by_iso[iso3].append(row)

    for row in admin1_rows:
        iso3 = clean_string(row.get("ISO3"))
        if iso3:
            admin1_by_iso[iso3].append(row)

    all_isos = set(admin0_by_iso) | set(admin1_by_iso) | set(COUNTRY_NAME_FALLBACKS)
    for iso3 in all_isos:
        admin0_total = next(
            (
                row
                for row in admin0_by_iso.get(iso3, [])
                if clean_string(row.get("Population_group")) == "T_TL"
            ),
            None,
        )
        admin0_any = admin0_by_iso.get(iso3, [None])[0]
        admin1_total = next(
            (
                row
                for row in admin1_by_iso.get(iso3, [])
                if clean_string(row.get("Population_group")) == "T_TL"
            ),
            None,
        )

        admin0_total_name = clean_string(admin0_total.get("Country")) if admin0_total else None
        admin0_any_name = clean_string(admin0_any.get("Country")) if admin0_any else None
        admin1_total_name = clean_string(admin1_total.get("Country")) if admin1_total else None
        static_fallback_name = COUNTRY_NAME_FALLBACKS.get(iso3)

        if admin0_total_name:
            best_name = admin0_total_name
            used_name_fallback = False
        elif admin0_any_name:
            best_name = admin0_any_name
            used_name_fallback = False
        elif admin1_total_name:
            best_name = admin1_total_name
            used_name_fallback = False
        else:
            best_name = static_fallback_name
            used_name_fallback = True

        best_population = choose_first_non_null(
            [
                parse_int(admin0_total.get("Population")) if admin0_total else None,
                parse_int(admin1_total.get("Population")) if admin1_total else None,
            ]
        )

        best_reference_year = choose_first_non_null(
            [
                parse_int(admin0_total.get("Reference_year")) if admin0_total else None,
                parse_int(admin1_total.get("Reference_year")) if admin1_total else None,
            ]
        )

        best_source = choose_first_non_null(
            [
                clean_string(admin0_total.get("Source")) if admin0_total else None,
                clean_string(admin1_total.get("Source")) if admin1_total else None,
            ]
        )

        reference[iso3] = {
            "country_name": best_name,
            "cod_population_total": best_population,
            "cod_population_reference_year": best_reference_year,
            "cod_population_source": best_source,
            "used_admin1_fallback": admin0_total is None and admin1_total is not None,
            "used_name_fallback": used_name_fallback,
        }

    return reference


def load_hrp_plans() -> Dict[str, List[Dict[str, Any]]]:
    rows = read_csv(HRP_FILE)
    by_country: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    for row in rows:
        code = clean_string(row.get("code"))
        if code is None or code.startswith("#"):
            continue
        years = parse_int(row.get("years"))
        if years != SCOPE_YEAR:
            continue

        locations = parse_locations(row.get("locations"))
        plan = {
            "plan_code": code,
            "internal_id": clean_string(row.get("internalId")),
            "plan_name": clean_string(row.get("planVersion")),
            "categories": clean_string(row.get("categories")),
            "location_codes": locations,
            "location_count": len(locations),
            "is_regional": len(locations) > 1,
            "start_date": clean_string(row.get("startDate")),
            "end_date": clean_string(row.get("endDate")),
            "orig_requirements_usd": parse_float(row.get("origRequirements")),
            "revised_requirements_usd": parse_float(row.get("revisedRequirements")),
        }
        for iso3 in locations:
            by_country[iso3].append(plan)

    return by_country


def load_fts_plan_data() -> Dict[str, Any]:
    rows = read_csv(FTS_PLAN_FILE)
    plans_by_country: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    history_by_country_year: Dict[str, Dict[int, Dict[str, Any]]] = defaultdict(dict)

    for row in rows:
        iso3 = clean_string(row.get("countryCode"))
        year = parse_int(row.get("year"))
        if iso3 is None or year is None:
            continue
        if year > SCOPE_YEAR:
            continue

        code = clean_string(row.get("code"))
        is_primary_plan_row = bool(code)
        requirements = parse_float(row.get("requirements"))
        funding = parse_float(row.get("funding"))
        percent_funded = parse_float(row.get("percentFunded"))

        year_entry = history_by_country_year[iso3].setdefault(
            year,
            {
                "year": year,
                "real_plan_count": 0,
                "requirements_usd": 0.0,
                "funding_usd": 0.0,
                "unattributed_funding_usd": 0.0,
                "unattributed_row_count": 0,
                "plan_codes": [],
            },
        )

        if is_primary_plan_row:
            year_entry["real_plan_count"] += 1
            year_entry["requirements_usd"] += requirements or 0.0
            year_entry["funding_usd"] += funding or 0.0
            if code not in year_entry["plan_codes"]:
                year_entry["plan_codes"].append(code)
        else:
            year_entry["unattributed_funding_usd"] += funding or 0.0
            year_entry["unattributed_row_count"] += 1

        if year != SCOPE_YEAR or not is_primary_plan_row:
            continue

        plan = {
            "plan_code": code,
            "plan_id": clean_string(row.get("id")),
            "plan_name": clean_string(row.get("name")),
            "plan_type": clean_string(row.get("typeName")) or "",
            "type_id": clean_string(row.get("typeId")),
            "requirements_usd": requirements,
            "funding_usd": funding,
            "percent_funded": percent_funded,
            "start_date": clean_string(row.get("startDate")),
            "end_date": clean_string(row.get("endDate")),
        }
        plans_by_country[iso3].append(plan)

    for iso3, year_map in history_by_country_year.items():
        for year_entry in year_map.values():
            requirements = year_entry["requirements_usd"]
            funding = year_entry["funding_usd"]
            year_entry["requirements_usd"] = round(requirements, 2)
            year_entry["funding_usd"] = round(funding, 2)
            year_entry["unattributed_funding_usd"] = round(
                year_entry["unattributed_funding_usd"], 2
            )
            year_entry["percent_funded"] = (
                round((100.0 * funding / requirements), 2) if requirements else None
            )
            year_entry["plan_codes"].sort()

    return {
        "plans_by_country": plans_by_country,
        "history_by_country": {
            iso3: sorted(year_map.values(), key=lambda item: item["year"])
            for iso3, year_map in history_by_country_year.items()
        },
    }


def choose_primary_plan(plans: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not plans:
        return None

    def ranking(plan: Dict[str, Any]) -> Any:
        plan_type = plan.get("plan_type") or ""
        return (
            PRIMARY_PLAN_TYPE_PRIORITY.get(plan_type, 99),
            sort_key_none_last(-(plan.get("requirements_usd") or 0.0)),
            plan.get("plan_code") or "",
        )

    return sorted(plans, key=ranking)[0]


def load_cluster_funding(file_path: Path) -> Dict[str, List[Dict[str, Any]]]:
    rows = read_csv(file_path)
    by_country: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    for row in rows:
        iso3 = clean_string(row.get("countryCode"))
        year = parse_int(row.get("year"))
        code = clean_string(row.get("code"))
        if iso3 is None or year != SCOPE_YEAR or code is None:
            continue

        by_country[iso3].append(
            {
                "plan_code": code,
                "plan_id": clean_string(row.get("id")),
                "plan_name": clean_string(row.get("name")),
                "cluster_code": clean_string(row.get("clusterCode")),
                "cluster_name": clean_string(row.get("cluster")),
                "requirements_usd": parse_float(row.get("requirements")),
                "funding_usd": parse_float(row.get("funding")),
                "percent_funded": parse_float(row.get("percentFunded")),
            }
        )

    for entries in by_country.values():
        entries.sort(
            key=lambda item: (
                item.get("plan_code") or "",
                item.get("cluster_name") or "",
            )
        )

    return by_country


def summarise_flow_file(file_path: Path, flow_name: str) -> Dict[str, Dict[str, Any]]:
    rows = read_csv(file_path)
    by_plan: Dict[str, Dict[str, Any]] = {}

    for row in rows:
        if parse_int(row.get("budgetYear")) != SCOPE_YEAR:
            continue
        plan_code = clean_string(row.get("destPlanCode"))
        if plan_code is None:
            continue

        amount_usd = parse_float(row.get("amountUSD")) or 0.0
        summary = by_plan.setdefault(
            plan_code,
            {
                "flow_name": flow_name,
                "row_count": 0,
                "amount_usd": 0.0,
                "donor_counter": Counter(),
                "organization_type_counter": Counter(),
                "cluster_counter": Counter(),
            },
        )
        summary["row_count"] += 1
        summary["amount_usd"] += amount_usd

        donor = clean_string(row.get("srcOrganization"))
        if donor:
            summary["donor_counter"][donor] += amount_usd

        donor_type = clean_string(row.get("srcOrganizationTypes"))
        if donor_type:
            summary["organization_type_counter"][donor_type] += amount_usd

        cluster_text = clean_string(row.get("destGlobalClusters"))
        if cluster_text:
            for cluster in parse_locations(cluster_text):
                summary["cluster_counter"][cluster] += amount_usd

    normalized: Dict[str, Dict[str, Any]] = {}
    for plan_code, summary in by_plan.items():
        normalized[plan_code] = {
            "flow_name": flow_name,
            "row_count": summary["row_count"],
            "amount_usd": round(summary["amount_usd"], 2),
            "top_donors": [
                {"name": name, "amount_usd": round(amount, 2)}
                for name, amount in summary["donor_counter"].most_common(5)
            ],
            "top_source_types": [
                {"name": name, "amount_usd": round(amount, 2)}
                for name, amount in summary["organization_type_counter"].most_common(5)
            ],
            "top_clusters": [
                {"name": name, "amount_usd": round(amount, 2)}
                for name, amount in summary["cluster_counter"].most_common(5)
            ],
        }

    return normalized


def attach_flow_summaries(
    plan_code: Optional[str],
    incoming: Dict[str, Dict[str, Any]],
    outgoing: Dict[str, Dict[str, Any]],
    internal: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    if plan_code is None:
        return {
            "plan_code": None,
            "incoming": None,
            "outgoing": None,
            "internal": None,
        }

    return {
        "plan_code": plan_code,
        "incoming": incoming.get(plan_code),
        "outgoing": outgoing.get(plan_code),
        "internal": internal.get(plan_code),
    }


def build_flow_summaries_by_plan(
    plans: List[Dict[str, Any]],
    incoming: Dict[str, Dict[str, Any]],
    outgoing: Dict[str, Dict[str, Any]],
    internal: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    return [
        {
            "plan_code": plan["plan_code"],
            "plan_name": plan.get("plan_name"),
            "incoming": incoming.get(plan["plan_code"]),
            "outgoing": outgoing.get(plan["plan_code"]),
            "internal": internal.get(plan["plan_code"]),
        }
        for plan in plans
    ]


def summarise_cbpf_allocations() -> Dict[str, Any]:
    rows = read_csv(CBPF_ALLOCATIONS_FILE)
    total_budget_by_year: Counter = Counter()
    budget_by_cluster_2026: Counter = Counter()
    budget_by_agency_2026: Counter = Counter()

    for row in rows:
        year = parse_int(row.get("Year"))
        budget = parse_float(row.get("Budget")) or 0.0
        cluster = clean_string(row.get("Cluster")) or "Unknown"
        agency = clean_string(row.get("Agency")) or "Unknown"
        if year is None:
            continue
        total_budget_by_year[year] += budget
        if year == SCOPE_YEAR:
            budget_by_cluster_2026[cluster] += budget
            budget_by_agency_2026[agency] += budget

    return {
        "rows": len(rows),
        "total_budget_by_year": [
            {"year": year, "budget_usd": round(amount, 2)}
            for year, amount in sorted(total_budget_by_year.items())
        ],
        "top_clusters_2026": [
            {"cluster": name, "budget_usd": round(amount, 2)}
            for name, amount in budget_by_cluster_2026.most_common(10)
        ],
        "top_agencies_2026": [
            {"agency": name, "budget_usd": round(amount, 2)}
            for name, amount in budget_by_agency_2026.most_common(10)
        ],
    }


def summarise_cbpf_contributions() -> Dict[str, Any]:
    rows = read_csv(CBPF_CONTRIBUTIONS_FILE)
    total_by_year: Counter = Counter()
    donor_totals_2026: Counter = Counter()
    donor_type_totals_2026: Counter = Counter()
    paid_2026 = 0.0
    pledged_2026 = 0.0

    for row in rows:
        year = parse_int(row.get("Year"))
        total = parse_float(row.get("Total")) or 0.0
        if year is None:
            continue
        total_by_year[year] += total
        if year == SCOPE_YEAR:
            donor = clean_string(row.get("Donor")) or "Unknown"
            donor_type = clean_string(row.get("Donor type")) or "Unknown"
            donor_totals_2026[donor] += total
            donor_type_totals_2026[donor_type] += total
            paid_2026 += parse_float(row.get("Paid")) or 0.0
            pledged_2026 += parse_float(row.get("Pledged")) or 0.0

    return {
        "rows": len(rows),
        "total_by_year": [
            {"year": year, "total_usd": round(amount, 2)}
            for year, amount in sorted(total_by_year.items())
        ],
        "paid_2026_usd": round(paid_2026, 2),
        "pledged_2026_usd": round(pledged_2026, 2),
        "top_donors_2026": [
            {"donor": name, "total_usd": round(amount, 2)}
            for name, amount in donor_totals_2026.most_common(10)
        ],
        "donor_types_2026": [
            {"donor_type": name, "total_usd": round(amount, 2)}
            for name, amount in donor_type_totals_2026.most_common()
        ],
    }


def build_country_record(
    iso3: str,
    hno_data: Dict[str, Dict[str, Any]],
    cod_reference: Dict[str, Dict[str, Any]],
    hrp_by_country: Dict[str, List[Dict[str, Any]]],
    fts_plans_by_country: Dict[str, List[Dict[str, Any]]],
    fts_history_by_country: Dict[str, List[Dict[str, Any]]],
    cluster_raw_by_country: Dict[str, List[Dict[str, Any]]],
    cluster_global_by_country: Dict[str, List[Dict[str, Any]]],
    incoming_by_plan: Dict[str, Dict[str, Any]],
    outgoing_by_plan: Dict[str, Dict[str, Any]],
    internal_by_plan: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    hno_country = hno_data[iso3]
    hno_all = hno_country.get("all_row") or {}
    cod = cod_reference.get(iso3, {})
    hrp_plans = sorted(
        hrp_by_country.get(iso3, []),
        key=lambda item: (item["plan_code"], item["plan_name"] or ""),
    )
    fts_plans = sorted(
        fts_plans_by_country.get(iso3, []),
        key=lambda item: (item["plan_code"], item["plan_name"] or ""),
    )
    primary_plan = choose_primary_plan(fts_plans)
    country_name = choose_first_non_null(
        [
            cod.get("country_name"),
            COUNTRY_NAME_FALLBACKS.get(iso3),
        ]
    )

    return {
        "iso3": iso3,
        "country_name": country_name,
        "reference": {
            "hno_population_2026": hno_all.get("population"),
            "cod_population_total": cod.get("cod_population_total"),
            "cod_population_reference_year": cod.get("cod_population_reference_year"),
            "cod_population_source": cod.get("cod_population_source"),
            "used_admin1_reference_fallback": cod.get("used_admin1_fallback", False),
            "used_country_name_fallback": cod.get("used_name_fallback", False),
        },
        "hno": {
            "description": hno_all.get("description"),
            "category": hno_all.get("category"),
            "people_in_need": hno_all.get("people_in_need"),
            "targeted": hno_all.get("targeted"),
            "affected": hno_all.get("affected"),
            "reached": hno_all.get("reached"),
            "info": hno_all.get("info"),
            "source_year": SCOPE_YEAR,
        },
        "hno_sectors": sorted(
            hno_country.get("sector_rows", []),
            key=lambda item: (item.get("cluster_code") or "", item.get("description") or ""),
        ),
        "hrp_2026": hrp_plans,
        "fts_plans_2026": fts_plans,
        "primary_plan_2026": primary_plan,
        "flow_summaries_by_plan_2026": build_flow_summaries_by_plan(
            fts_plans,
            incoming_by_plan,
            outgoing_by_plan,
            internal_by_plan,
        ),
        "funding_flows_2026": attach_flow_summaries(
            primary_plan.get("plan_code") if primary_plan else None,
            incoming_by_plan,
            outgoing_by_plan,
            internal_by_plan,
        ),
        "sector_funding_2026": {
            "global_cluster_schema": cluster_global_by_country.get(iso3, []),
            "raw_cluster_schema": cluster_raw_by_country.get(iso3, []),
        },
        "history": {
            "fts_country_year_totals": fts_history_by_country.get(iso3, []),
        },
    }


def build_report(countries: List[Dict[str, Any]]) -> Dict[str, Any]:
    countries_without_primary_plan = [
        country["iso3"]
        for country in countries
        if country.get("primary_plan_2026") is None
    ]
    countries_using_name_fallback = [
        country["iso3"]
        for country in countries
        if country["reference"].get("used_country_name_fallback")
    ]
    countries_missing_cod_population = [
        country["iso3"]
        for country in countries
        if country["reference"].get("cod_population_total") is None
    ]
    countries_missing_hno_all = [
        country["iso3"]
        for country in countries
        if country["hno"].get("people_in_need") is None
    ]

    countries_with_multiple_fts_plans = [
        {
            "iso3": country["iso3"],
            "plan_codes": [plan["plan_code"] for plan in country["fts_plans_2026"]],
        }
        for country in countries
        if len(country["fts_plans_2026"]) > 1
    ]

    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope_year": SCOPE_YEAR,
        "country_count": len(countries),
        "countries_without_primary_plan": countries_without_primary_plan,
        "countries_missing_hno_all_row": countries_missing_hno_all,
        "countries_missing_cod_population": countries_missing_cod_population,
        "countries_using_country_name_fallback": countries_using_name_fallback,
        "countries_with_multiple_fts_plans_2026": countries_with_multiple_fts_plans,
        "notes": [
            "The aggregated JSON is country-centered because HNO is country-level and sector detail is nested below it.",
            "HNO sector rows are preserved separately and are not summed into national totals.",
            "FTS rows with blank plan codes are treated as unattributed country-level funding in history and excluded from primary plan selection.",
            "CBPF allocations and contributions summary CSVs are included under global summaries because they do not contain a reliable country join key in their visible schema.",
        ],
    }


def main() -> None:
    hno_data = load_hno_data()
    cod_reference = load_cod_reference()
    hrp_by_country = load_hrp_plans()

    fts_plan_data = load_fts_plan_data()
    fts_plans_by_country = fts_plan_data["plans_by_country"]
    fts_history_by_country = fts_plan_data["history_by_country"]

    cluster_raw_by_country = load_cluster_funding(FTS_CLUSTER_FILE)
    cluster_global_by_country = load_cluster_funding(FTS_GLOBAL_CLUSTER_FILE)

    incoming_by_plan = summarise_flow_file(FTS_INCOMING_FILE, "incoming")
    outgoing_by_plan = summarise_flow_file(FTS_OUTGOING_FILE, "outgoing")
    internal_by_plan = summarise_flow_file(FTS_INTERNAL_FILE, "internal")

    countries = [
        build_country_record(
            iso3=iso3,
            hno_data=hno_data,
            cod_reference=cod_reference,
            hrp_by_country=hrp_by_country,
            fts_plans_by_country=fts_plans_by_country,
            fts_history_by_country=fts_history_by_country,
            cluster_raw_by_country=cluster_raw_by_country,
            cluster_global_by_country=cluster_global_by_country,
            incoming_by_plan=incoming_by_plan,
            outgoing_by_plan=outgoing_by_plan,
            internal_by_plan=internal_by_plan,
        )
        for iso3 in sorted(hno_data)
    ]

    payload = {
        "meta": {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "scope_year": SCOPE_YEAR,
            "source_folder": str(DATA_DIR),
            "primary_country_source": HNO_FILE.name,
            "country_count": len(countries),
            "source_files_used": [
                HNO_FILE.name,
                COD_ADMIN0_FILE.name,
                COD_ADMIN1_FILE.name,
                HRP_FILE.name,
                FTS_PLAN_FILE.name,
                FTS_CLUSTER_FILE.name,
                FTS_GLOBAL_CLUSTER_FILE.name,
                FTS_INCOMING_FILE.name,
                FTS_OUTGOING_FILE.name,
                FTS_INTERNAL_FILE.name,
                CBPF_ALLOCATIONS_FILE.name,
                CBPF_CONTRIBUTIONS_FILE.name,
            ],
            "source_files_intentionally_not_used_as_inputs": [
                "2026_crisis_summary.csv",
                "fts_requirements_funding_covid_global.csv",
                "cod_population_admin4.csv",
            ],
            "notes": [
                "This artifact is intended as a normalized intermediate layer for ranking and query execution.",
                "Country-level need comes from HNO 2026 ALL rows; sector rows are nested separately.",
                "Country population is stored twice when available: HNO crisis-year population and COD reference population.",
                "The JSON preserves both normalized global cluster funding labels and the raw cluster schema labels from FTS.",
            ],
        },
        "global_summaries": {
            "cbpf_allocations": summarise_cbpf_allocations(),
            "cbpf_contributions": summarise_cbpf_contributions(),
        },
        "countries": countries,
    }

    report = build_report(countries)

    OUTPUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n")
    REPORT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=True) + "\n")

    print(f"Wrote {OUTPUT_JSON}")
    print(f"Wrote {REPORT_JSON}")
    print(f"Countries aggregated: {len(countries)}")


if __name__ == "__main__":
    main()
