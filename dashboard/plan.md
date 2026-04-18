# System Architecture & Engineering Document: Humanitarian Crisis Dashboard

## 1. Project Overview & Philosophy
**Goal:** Build a frontend dashboard to help the UN allocate funds by analyzing global humanitarian crises. 

**Philosophy:** Optimize for rapid development and maximum backend control. This is a Server-Side Rendered (SSR) "Thin Client" architecture. Business logic, data filtering, and layout structure are controlled by Python. The frontend uses minimal custom JavaScript, relying on HTMX for interactivity and Tailwind CSS for styling.


## 2. Tech Stack
* **Backend:** Python with FastAPI (Fast, async, built-in schema handling).
* **Database:** A single local JSON file loaded into memory.
* **Frontend Interactivity:** HTMX (fetched via CDN).
* **Styling:** Tailwind CSS (fetched via CDN script for zero build-step).
* **Mapping:** Leaflet.js (fetched via CDN). No API keys required.


## 3. Data Architecture (The "Core + Metadata" Pattern)
The underlying data is a list of JSON objects representing crises. Because data features are highly volatile, the schema is divided into "strict" mapping fields (which the UI relies on to function) and "flexible" metadata fields (which the UI will just loop through blindly).

| Top-Level Field | Sub-Field | Data Type | Purpose & Description |
| :--- | :--- | :--- | :--- |
| **`id`** | - | `String` / `Int` | Unique identifier for the crisis. |
| **`display`** | `title` | `String` | Primary name of the crisis. |
| | `lat` | `Float` | Latitude for map placement. |
| | `lng` | `Float` | Longitude for map placement. |
| | `radius_metric`| `Float` | Numeric value used to calculate the Leaflet circle size (e.g., total affected population). |
| | `color_metric` | `Float` | Numeric value used to calculate the Leaflet circle color gradient (e.g., severity scale 1-10). |
| **`summary`** | `brief_text` | `String` | Short descriptive string for the map hover tooltip and the list item card. |
| | `key_stat_1` | `String` | Top highlight statistic (e.g., "1.2M Displaced"). |
| | `key_stat_2` | `String` | Secondary highlight statistic (e.g., "Critical Water Shortage"). |
| **`metadata`** | `[dynamic_keys]` | `Any` | A flexible dictionary. The data team can dump any scraped metric here. The Python backend will dynamically iterate through these keys to build the side panel table without needing frontend updates. |


## 4. UI/UX Layout & Component Behavior
The UI must be modern, professional, and responsive, featuring a top control panel and a main view area with two tabs (Map and List). 

### A. Top Panel (Always Visible)
* Contains a search text input and dynamic dropdowns for filtering/sorting.
* **Engineering Rule:** The available filtering/sorting options are passed from the backend. All search/filter events trigger an HTMX request to update the active tab content.

### B. View Area: Map Tab (Default)
* Takes up all remaining vertical/horizontal space below the top panel.
* **Markers:** Leaflet circles superimposed over the map.
    * *Radius* is calculated via `display.radius_metric`.
    * *Color* is calculated via `display.color_metric`.
* **Hover:** Triggers a Leaflet tooltip showing the `display.title` and data from the `summary` object.
* **Click:** Triggers an HTMX request to fetch the side panel and slides it into view.

### C. View Area: List Tab
* A scrollable vertical list of cards.
* Each card displays the `display.title` and the `summary` data (mirroring the map hover tooltip).
* **Click:** Triggers an HTMX request to fetch the side panel, sliding it into view while leaving the right side of the list visible.

### D. The Side Panel (Details View)
* **Animation:** Slides in from the left edge of the screen (using Tailwind classes like `fixed`, `left-0`, `h-full`, `-translate-x-full` -> `translate-x-0`, `transition-transform`). Covers the map or partially covers the list.
* **Content:** Auto-generated key-value UI. The backend loops through the `metadata` dictionary and generates HTML rows/cards. Needs a prominent "Close/X" button to slide it back out.


## 5. API Endpoints (FastAPI)

| Endpoint | Method | Response Type | Purpose |
| :--- | :--- | :--- | :--- |
| `/` | `GET` | `text/html` | Serves `index.html`. Injects the base layout, top panel, and initial filter configs. |
| `/api/map-data` | `GET` | `application/json` | Fetches the full JSON dataset for Leaflet to render the circles on load. |
| `/list` | `GET` | `text/html` | Accepts query params (`?search=x&sort=y`). Filters/sorts data in Python, returns an HTML fragment of `<li>` elements. HTMX injects this into the list container. |
| `/details/{id}`| `GET` | `text/html` | Returns an HTML fragment (the contents of the Side Panel) containing the dynamic `metadata` dump. HTMX injects this into the side panel container. |


## 6. Implementation Instructions for AI Generator

When generating the code from this document, adhere STRICTLY to the following constraints:

1.  **Zero Build Steps:** Do not use Node.js, Webpack, Vite, or npm. Include HTMX, Tailwind, and Leaflet strictly via `<script>` and `<link>` CDN tags in the main `index.html` file.
2.  **Logic Separation:** Do not write filtering or sorting logic in JavaScript. JS is ONLY allowed for initializing Leaflet and wiring Leaflet click events to `htmx.ajax()` calls.
3.  **Tailwind Sliding Panel:** Implement the side panel using a fixed div on the left. Use a snippet of vanilla JS triggered by HTMX events or a close button to toggle a `.translate-x-0` class for the slide-in effect.
4.  **Dynamic Rendering:** Ensure the `/details/{id}` endpoint in FastAPI iterates blindly over the `metadata` object to build the HTML table/list. It should not look for hardcoded keys, ensuring total flexibility for the data team.
5.  **Project Structure:** Keep it simple. 
    * `main.py` (FastAPI app and routing)
    * `data.json` (Mock dataset)
    * `templates/` (Folder for Jinja2 HTML templates: `index.html`, `list_items.html`, `side_panel.html`)