from nlp_service import (
    QueryParser,
    QueryFilter,
    NumericCondition,
    ListCondition,
)
import json
import os
import math
from fastapi import FastAPI, Request, Query, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from typing import Optional, List, Any
from dotenv import load_dotenv
from filter_chips import build_filter_chips
from field_labels import FIELD_LABELS
from regions import expand_location_values

load_dotenv()

app = FastAPI(title="Humanitarian Crisis Dashboard")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
nlp_parser = QueryParser()

# --- Declarative Configuration ---

# Maps QueryFilter attribute names to paths in the crisis dictionary
FIELD_MAP = {
    "locations": [["location_codes"], ["country_iso3"], ["primary_location_code"]],
    "people_in_need": [["people_in_need"]],
    "funding_coverage_percentage": [["percent_funded"]],
    "funding_required_usd": [["requirements"]],
    "funding_received_usd": [["funding"]],
    "overlooked_rank": [],
    "crisis_type": []
}

CHIP_FIELD_ORDER = list(FIELD_MAP.keys())

SORT_FIELDS = [
    "people_in_need",
    "funding_coverage_percentage",
    "funding_required_usd",
    "funding_received_usd",
]

SORT_FIELD_OPTIONS = [
    {
        "value": field_name,
        "label": FIELD_LABELS.get(field_name, {}).get("long", field_name.replace("_", " ").title()),
    }
    for field_name in SORT_FIELDS
]

def get_nested_value(data: dict, path: List[str]) -> Any:
    """Safely retrieves a value from a nested dictionary given a path list."""
    current = data
    for key in path:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return None
    return current


def sanitize_non_finite_values(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: sanitize_non_finite_values(v) for k, v in value.items()}
    if isinstance(value, list):
        return [sanitize_non_finite_values(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


# --- Dynamic Core Logic ---

def calculate_color(funding_coverage: float) -> str:
    if funding_coverage < 10: return "#b91c1c"
    if funding_coverage < 25: return "#f97316"
    return "#facc15"

def calculate_radius(people_in_need: int) -> float:
    people_in_need = max(0, people_in_need)

    min_radius_km = 30.0
    max_radius_km = 200.0
    midpoint = 2_200_000
    steepness = 1_000_000

    return min_radius_km + (max_radius_km - min_radius_km) / (1 + math.exp(-(people_in_need - midpoint) / steepness))


def _normalize_crisis_record(crisis: dict) -> Optional[dict]:
    # Dashboard expects the all-years schema with a top-level years dictionary.
    if "years" not in crisis or not isinstance(crisis.get("years"), dict):
        return None

    years = crisis.get("years", {})
    if "2026" not in years:
        return None

    year_data = years["2026"]
    project_metrics_2026 = crisis.get("project_metrics_2026")
    if not isinstance(project_metrics_2026, dict):
        return None
    codes = year_data.get("codes") or []
    names = year_data.get("names") or []
    primary_location_name = crisis.get("primary_location_name")
    impacted_countries = crisis.get("location_names") or []
    if not impacted_countries and primary_location_name:
        impacted_countries = [primary_location_name]
    location_codes = crisis.get("location_codes") or []
    if not location_codes and crisis.get("primary_location_code"):
        location_codes = [crisis.get("primary_location_code")]
    people_2026 = crisis.get("people_2026") or {}
    funding_timeline = []
    for year_key, values in years.items():
        try:
            year_int = int(year_key)
        except (TypeError, ValueError):
            continue

        requirements = values.get("requirements")
        funding = values.get("funding")
        if requirements is None and funding is None:
            continue

        coverage_ratio = 0.0
        if isinstance(requirements, (int, float)) and isinstance(funding, (int, float)) and requirements > 0:
            coverage_ratio = max(0.0, min(float(funding) / float(requirements), 1.0))

        avg_percent_funded = values.get("avg_percent_funded")
        avg_coverage_ratio = None
        if isinstance(avg_percent_funded, (int, float)):
            avg_coverage_ratio = max(0.0, min(float(avg_percent_funded) / 100.0, 1.0))

        funding_timeline.append(
            {
                "year": year_int,
                "requirements": requirements,
                "funding": funding,
                "percent_funded": values.get("percent_funded"),
                "coverage_ratio": coverage_ratio,
                "avg_percent_funded": avg_percent_funded,
                "avg_coverage_ratio": avg_coverage_ratio,
            }
        )

    funding_timeline.sort(key=lambda x: x["year"])

    normalized = {
        "code": codes[0] if codes else crisis.get("funding_base_key"),
        "dest_plan_code": codes[0] if codes else crisis.get("funding_base_key"),
        "name": names[0] if names else crisis.get("funding_base_key"),
        "display_year": 2026,
        "primary_location_code": crisis.get("primary_location_code"),
        "primary_location_name": crisis.get("primary_location_name"),
        "location_codes": location_codes,
        "location_names": impacted_countries,
        "requirements": year_data.get("requirements"),
        "funding": year_data.get("funding"),
        "percent_funded": year_data.get("percent_funded"),
        "contribution_count": year_data.get("contribution_count"),
        "category_breakdown_scored": project_metrics_2026.get("category_breakdown_scored") or [],
        "category_level_score": project_metrics_2026.get("category_level_score"),
        "overall_severity_score": project_metrics_2026.get("overall_severity_score"),
        "systematic_underfunding": crisis.get("systematic_underfunding"),
        "people_in_need": people_2026.get("people_in_need"),
        "people_targeted": people_2026.get("people_targeted"),
        "people_affected": people_2026.get("people_affected"),
        "people_reached": people_2026.get("people_reached"),
        "latitude": crisis.get("latitude"),
        "longitude": crisis.get("longitude"),
        "funding_base_key": crisis.get("funding_base_key"),
        "funding_timeline": funding_timeline,
    }
    return normalized

def get_enriched_data():
    json_path = os.path.join(
        BASE_DIR, "..", "data_pipeline", "crisis_summary_all_years.json"
    )
    if not os.path.exists(json_path):
        raise FileNotFoundError(
            "Could not find data_pipeline/crisis_summary_all_years.json."
        )

    with open(json_path, "r") as f:
        raw_data = json.load(f)

    data = [_normalize_crisis_record(item) for item in raw_data]
    data = [item for item in data if item is not None]
    
    valid_data = []
    for crisis in data:
        if crisis.get("latitude") is not None and crisis.get("longitude") is not None:
            primary_location_name = crisis.get("primary_location_name")
            full_location_names = crisis.get("location_names") or []
            if not full_location_names and primary_location_name:
                full_location_names = [primary_location_name]
            full_location_names = [name for name in full_location_names if name]

            crisis["primary_location_name_display"] = primary_location_name
            crisis["location_names_display"] = full_location_names
            crisis["locations_display"] = ", ".join(full_location_names)

            crisis["color"] = calculate_color(crisis.get("percent_funded") or 0)
            crisis["radius_km"] = calculate_radius(crisis.get("people_in_need") or 500000)
            valid_data.append(sanitize_non_finite_values(crisis))
    return valid_data

def apply_advanced_filters(data: List[dict], filters: Optional[QueryFilter]) -> List[dict]:
    if not filters:
        return data

    filtered_results = data

    available_iso3: set[str] = set()
    for crisis in data:
        primary = crisis.get("primary_location_code")
        if isinstance(primary, str) and primary:
            available_iso3.add(primary.upper())
        country_iso3 = crisis.get("country_iso3")
        if isinstance(country_iso3, str) and country_iso3:
            available_iso3.add(country_iso3.upper())
        for code in crisis.get("location_codes") or []:
            if isinstance(code, str) and code:
                available_iso3.add(code.upper())
    
    # 1. Declarative Filtering Loop
    for field_name, condition in filters.model_dump(exclude_none=True).items():
        if field_name == "order_by": continue
        
        paths = FIELD_MAP.get(field_name)
        if not paths: continue

        condition_obj = getattr(filters, field_name)
        if field_name == "locations" and isinstance(condition_obj, ListCondition):
            expanded_values = expand_location_values(condition_obj.values, available_iso3)
            condition_obj = ListCondition(values=expanded_values, exclude=condition_obj.exclude)
        
        def item_matches(crisis):
            values_to_check = []
            for path in paths: # type: ignore
                val = get_nested_value(crisis, path)
                if val is None:
                    continue
                if isinstance(val, list):
                    values_to_check.extend(val)
                else:
                    values_to_check.append(val)

            if not values_to_check:
                if isinstance(condition_obj, NumericCondition) and condition_obj.operator in {"gt", "lt", "gte", "lte"}:
                    return True
                return False

            if getattr(condition_obj, "exclude", False):
                return all(condition_obj.evaluate(v) for v in values_to_check)

            return any(condition_obj.evaluate(v) for v in values_to_check)

        filtered_results = [c for c in filtered_results if item_matches(c)]

    # 2. Declarative Sorting
    if filters.order_by:
        field_name = filters.order_by.field
        paths = FIELD_MAP.get(field_name)
        if paths:
            path = paths[0]
            reverse = filters.order_by.direction == "desc"
            filtered_results.sort(key=lambda x: get_nested_value(x, path) or 0, reverse=reverse)

    return filtered_results

# --- Routes ---

@app.get("/", response_class=HTMLResponse)
async def get_index(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "chips": [],
            "filters_json": QueryFilter().model_dump_json(),
            "sort_field_options": SORT_FIELD_OPTIONS,
            "selected_sort_field": "",
            "selected_sort_direction": "desc",
        },
    )

@app.post("/nlp-query", response_class=HTMLResponse)
async def post_nlp_query(
    request: Request,
    query: Optional[str] = Form(None),
    current_filters: Optional[str] = Form(None),
    preserve_sort: bool = Form(False),
):
    # Handle empty or missing query safely
    if not query:
        parsed_filter = QueryFilter()
        if preserve_sort and current_filters:
            try:
                existing_filter = QueryFilter.model_validate_json(current_filters)
                parsed_filter.order_by = existing_filter.order_by
            except:
                pass
    else:
        parsed_filter = nlp_parser.parse_query(query)
    
    chips = build_filter_chips(parsed_filter, CHIP_FIELD_ORDER)
    selected_sort_field = parsed_filter.order_by.field if parsed_filter.order_by else ""
    selected_sort_direction = parsed_filter.order_by.direction.value if parsed_filter.order_by else "desc"

    # Trigger a refresh AFTER the DOM has been updated with the new filter JSON
    response = templates.TemplateResponse(
        request=request, 
        name="filter_chips.html", 
        context={
            "chips": chips,
            "filters_json": parsed_filter.model_dump_json(),
            "sort_field_options": SORT_FIELD_OPTIONS,
            "selected_sort_field": selected_sort_field,
            "selected_sort_direction": selected_sort_direction,
        }
    )
    response.headers["HX-Trigger-After-Swap"] = "filters-changed"
    return response

@app.get("/api/map-data")
async def get_map_data(filters: Optional[str] = Query(None)):
    data = get_enriched_data()
    if filters:
        try:
            f_obj = QueryFilter.model_validate_json(filters)
            data = apply_advanced_filters(data, f_obj)
        except: pass
    return JSONResponse(content=data)

@app.get("/list", response_class=HTMLResponse)
async def get_list(
    request: Request, 
    filters: Optional[str] = Query(None),
    selected_crisis_id: Optional[str] = Query(None)
):
    filtered_data = get_enriched_data()
    
    applied_nlp_sort = False
    if filters:
        try:
            f_obj = QueryFilter.model_validate_json(filters)
            filtered_data = apply_advanced_filters(filtered_data, f_obj)
            if f_obj.order_by:
                applied_nlp_sort = True
        except: pass
    
    if not applied_nlp_sort:
        filtered_data.sort(key=lambda x: get_nested_value(x, ["display", "title"]) or "")
    
    return templates.TemplateResponse(
        request=request, 
        name="list_items.html", 
        context={
            "crises": filtered_data,
            "selected_crisis_id": selected_crisis_id
        }
    )

@app.get("/details/{crisis_code}", response_class=HTMLResponse)
async def get_details(request: Request, crisis_code: str):
    data = get_enriched_data()
    crisis = next((c for c in data if c["code"] == crisis_code), None)
    if not crisis:
        return HTMLResponse(content="Crisis not found", status_code=404)
    return templates.TemplateResponse(request=request, name="side_panel.html", context={"crisis": crisis})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
