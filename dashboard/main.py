import json
from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from typing import Optional, List

app = FastAPI(title="Humanitarian Crisis Dashboard")
templates = Jinja2Templates(directory="dashboard/templates")

# Load data on startup
with open("dashboard/data.json", "r") as f:
    CRISES_DATA = json.load(f)

@app.get("/", response_class=HTMLResponse)
async def get_index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.get("/api/map-data")
async def get_map_data():
    return JSONResponse(content=CRISES_DATA)

@app.get("/list", response_class=HTMLResponse)
async def get_list(
    request: Request, 
    search: Optional[str] = Query(None), 
    sort: Optional[str] = Query("title")
):
    filtered_data = CRISES_DATA.copy()
    
    # Filtering logic
    if search:
        search = search.lower()
        filtered_data = [
            c for c in filtered_data 
            if search in c["display"]["title"].lower() or search in c["summary"]["brief_text"].lower()
        ]
    
    # Sorting logic
    if sort == "title":
        filtered_data.sort(key=lambda x: x["display"]["title"])
    elif sort == "severity":
        # Using color_metric as a proxy for severity
        filtered_data.sort(key=lambda x: x["display"]["color_metric"], reverse=True)
    elif sort == "impact":
        # Using radius_metric as a proxy for impact
        filtered_data.sort(key=lambda x: x["display"]["radius_metric"], reverse=True)

    return templates.TemplateResponse(
        request=request, 
        name="list_items.html", 
        context={"crises": filtered_data}
    )

@app.get("/details/{crisis_id}", response_class=HTMLResponse)
async def get_details(request: Request, crisis_id: str):
    crisis = next((c for c in CRISES_DATA if c["id"] == crisis_id), None)
    if not crisis:
        return HTMLResponse(content="Crisis not found", status_code=404)
    
    return templates.TemplateResponse(
        request=request, 
        name="side_panel.html", 
        context={"crisis": crisis}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
