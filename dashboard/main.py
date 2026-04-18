from nlp_service import QueryParser, QueryFilter
import json
import os
from fastapi import FastAPI, Request, Query, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from typing import Optional, List, Any
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Humanitarian Crisis Dashboard")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
nlp_parser = QueryParser()

# --- Declarative Configuration ---

# Maps QueryFilter attribute names to paths in the crisis dictionary
FIELD_MAP = {
    "locations": [["location_codes"], ["country_iso3"], ["locations"]],
    "people_in_need": [["people_in_need"]],
    "funding_coverage_percentage": [["percent_funded"]],
    "funding_required_usd": [["requirements"]],
    "funding_received_usd": [["funding"]],
    "overlooked_rank": [],
    "crisis_type": []
}

def get_nested_value(data: dict, path: List[str]) -> Any:
    """Safely retrieves a value from a nested dictionary given a path list."""
    current = data
    for key in path:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return None
    return current

# --- Dynamic Core Logic ---

def calculate_color(funding_coverage: float) -> str:
    if funding_coverage < 10: return "#b91c1c"
    if funding_coverage < 25: return "#f97316"
    return "#facc15"

def calculate_radius(people_in_need: int) -> float:
    return people_in_need * 0.000025

def get_enriched_data():
    json_path = os.path.join(BASE_DIR, "..", "data", "2026_crisis_summary.json")
    with open(json_path, "r") as f:
        data = json.load(f)
    
    valid_data = []
    for crisis in data:
        if crisis.get("latitude") is not None and crisis.get("longitude") is not None:
            crisis["color"] = calculate_color(crisis.get("percent_funded") or 0)
            crisis["radius_km"] = calculate_radius(crisis.get("people_in_need") or 500000)
            valid_data.append(crisis)
    return valid_data

def apply_advanced_filters(data: List[dict], filters: Optional[QueryFilter]) -> List[dict]:
    print("Applying filters:", filters)
    if not filters:
        return data

    filtered_results = data
    
    # 1. Declarative Filtering Loop
    # We iterate over the fields actually populated in the filter object
    for field_name, condition in filters.model_dump(exclude_none=True).items():
        if field_name == "order_by": continue # Handle sorting separately
        
        paths = FIELD_MAP.get(field_name)
        if not paths: continue

        # Re-get the Pydantic condition object to use its .evaluate() method
        condition_obj = getattr(filters, field_name)
        
        def item_matches(crisis):
            # Check all possible paths for this field (e.g. Country Code OR Region)
            for path in paths: # type: ignore
                val = get_nested_value(crisis, path)
                if condition_obj.evaluate(val):
                    return True
            return False

        filtered_results = [c for c in filtered_results if item_matches(c)]

    # 2. Declarative Sorting
    if filters.order_by:
        field_name = filters.order_by.field
        paths = FIELD_MAP.get(field_name)
        if paths:
            # Sort based on the first mapped path for that field
            path = paths[0]
            reverse = filters.order_by.direction == "desc"
            filtered_results.sort(
                key=lambda x: get_nested_value(x, path) or 0, 
                reverse=reverse
            )

    return filtered_results

# --- Routes ---

@app.get("/", response_class=HTMLResponse)
async def get_index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.post("/nlp-query", response_class=HTMLResponse)
async def post_nlp_query(request: Request, query: str = Form(...)):
    parsed_filter = nlp_parser.parse_query(query)
    chips = []
    f_dict = parsed_filter.model_dump(exclude_none=True)
    
    if "locations" in f_dict:
        prefix = "Excluding" if parsed_filter.locations.exclude else "In" # type: ignore
        chips.append(f"{prefix}: {', '.join(parsed_filter.locations.values)}") # type: ignore
    if "people_in_need" in f_dict:
        chips.append(f"PIN {parsed_filter.people_in_need.operator} {parsed_filter.people_in_need.value:,}") # type: ignore
    if "funding_coverage_percentage" in f_dict:
        chips.append(f"Funding {parsed_filter.funding_coverage_percentage.operator} {parsed_filter.funding_coverage_percentage.value}%") # type: ignore
    if "order_by" in f_dict:
        chips.append(f"Sort: {parsed_filter.order_by.field} ({parsed_filter.order_by.direction})") # type: ignore

    return templates.TemplateResponse(
        request=request, 
        name="filter_chips.html", 
        context={"chips": chips, "filters_json": parsed_filter.model_dump_json()}
    )

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
async def get_list(request: Request, filters: Optional[str] = Query(None)):
    filtered_data = get_enriched_data()
    if filters:
        try:
            f_obj = QueryFilter.model_validate_json(filters)
            filtered_data = apply_advanced_filters(filtered_data, f_obj)
        except: pass
    else:
        filtered_data.sort(key=lambda x: get_nested_value(x, ["name"]) or "")
    
    return templates.TemplateResponse(request=request, name="list_items.html", context={"crises": filtered_data})

@app.get("/details/{crisis_id}", response_class=HTMLResponse)
async def get_details(request: Request, crisis_id: str):
    data = get_enriched_data()
    crisis = next((c for c in data if c["code"] == crisis_id), None)
    if not crisis:
        return HTMLResponse(content="Crisis not found", status_code=404)
    return templates.TemplateResponse(request=request, name="side_panel.html", context={"crisis": crisis})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
