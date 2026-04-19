# Technical write-up

## Data Sources and Input Files

The assessment pipeline consumes multiple humanitarian data sources stored in the `data/` directory:

- **Humanitarian Response Plans** (`humanitarian-response-plans.csv`): Contains plan metadata including `code`, `planVersion` (name), `year`, `primary_location`, `location_codes`, and `location_names`. This is the primary source for identifying which crisis plans exist.

- **Humanitarian Needs Overview** (`hpc_hno_2026.csv`): Provides sector-level needs estimates including `in_need` and `targeted` figures by category (education, food security, health, hygiene, protection, shelter, etc.). These category breakdowns feed into the sector gap scoring.

- **FTS Funding & Requirements Data** (`fts_requirements_funding_global.csv`): The main source of annual funding and requirement figures per plan. Includes columns for `code` (plan code), `year`, `requirements`, and `funding`.

- **CBPF Allocations** (`AllocationsByOrgType__20260419_002004_UTC.csv`): Country-based pooled fund allocations used to compute the `cbpf_gap` signal.

- **Contributions/Funding Flow Data** We wanted to use these but it was too lacking, it would be beneficial for the future if we want to add information such as (optional FTS incoming/outgoing/internal funding files) to cross-check funding flows.

The pipeline normalizes these disparate sources by matching plan codes and locations through a canonical key mapping process, which attempts to reconcile plan code changes, duplicate entries, and regional vs. country-level reporting over time.

## Data Processing and Missing Data Handling

When individual year data is missing or years are dropped, the pipeline applies fallback strategies to avoid losing historical context:

- **Requirement Projection Fallback**: If a year's requirement is missing or zero, the system constructs a projection called `requirements_last_year`. This is computed in `apply_last_year_requirement_fallback()` and `_fit_requirement_bootstrap_adjustments()`. The logic first extracts the previous year's unmet need: `requirements_last_year_raw = max(requirements[Y-1] - funding[Y-1], 0)`. Then a crisis-specific bootstrap adjustment is computed as the average year-to-year change in requirements across the crisis's historical record: `requirement_bootstrap_avg_delta = mean(requirements[Y] - requirements_last_year_raw[Y])` for all valid years. The projected requirement is then: `requirements_last_year = requirements_last_year_raw + requirement_bootstrap_avg_delta`. This combines the prior year's unmet need with the expected growth trajectory specific to each crisis, producing a more realistic fallback than raw historical carryover alone.

- **Category Breakdown Aggregation**: If category breakdowns are incomplete or inconsistent across years, the pipeline combines all available category rows for a given plan-year into a single aggregated breakdown. Only categories with positive `in_need` and non-null `targeted` are retained; missing or invalid entries are silently dropped.

- **Funding Ratio Calculation**: If either `requirements_effective` or `funding` is missing, the `percent_funded` is set to null, and the ratio-based gap signals are unavailable for that year. The system continues with other available signals.

- **Systematic Underfunding Score**: Computed from historical years where both a plan's `percent_funded` and the yearly average `percent_funded` are available. Years with missing values are excluded from the calculation. If fewer than two valid years are available, the score is set to null.

- **Peer Benchmark Calculation**: The system calculates a yearly average percent funded across all plans:

    avg_percent_funded_raw[year] = 100 * sum(funding for that year) / sum(requirements for that year)

If total requirements for a year are zero, the average is null. Plans with missing values in either numerator or denominator are excluded from the average.

The assessment module itself handles missing components gracefully. When a component (e.g., `funding_ratio_value`, `systematic_underfunding_score`, or `category_summary`) is unavailable, the logic:

1. Skips that component's direct signal.
2. Adds explicit driver evidence like `"Funding ratio data incomplete"` if the data gap is material.
3. Continues with remaining components to still produce a final band.

If nearly all components are missing, the system defaults to `"Some Funding Gaps"` and outputs a fallback driver `"Mixed or incomplete risk evidence"` with low confidence (0.3).

This approach ensures that incomplete data does not cause the system to crash, but it does add explicit uncertainty flags (low confidence values) to the rationale, signaling to dashboard users that the assessment is limited by data quality.

## Assessment Implementation Details 
The first is the funding ratio, which is a direct measure of how much of reported requirements is covered by delivered funding. This value is read from `crisis["percent_funded"]`, and the system interprets it through threshold rules such as below 5% for extreme underfunding, below 10% for critical underfunding, below 25% for low funding ratio, above 45% for strong coverage, and 80% or greater for adequacy.

A separate pressure signal is the raw funding gap, computed when both requirements and funding are present as:

    funding_gap = max(requirements - funding, 0)

This absolute gap is used as evidence of material demand pressure and appears in rationale selection if the gap exceeds large thresholds.

The pipeline also computes a historical benchmark signal called `systematic_underfunding_score`. That score is based on repeated annual comparisons between a plan's own percent funded and the peer-group average funding coverage in the same year, computed by `compute_systematic_underfunding_metrics()`. For each year in the historical record where both a plan's percent funded and the yearly average percent funded are available, the gap to benchmark is:

    gap_vs_benchmark = avg_percent_funded_raw - percent_funded
    underfunding_gap = max(gap_vs_benchmark, 0)

The underfunding gap captures how many percentage points below the peer average this plan fell. To aggregate across years, the system uses requirement-based weights. If the plan's multi-year requirements sum to a positive value, then:

    weights[i] = requirements[i] / sum(requirements)

If total requirements are zero or missing, equal weights are used across years. The eta-squared (effect-size) statistic is then computed:

    ss_under = sum(weights * underfunding_gap^2)
    ss_all = sum(weights * gap_vs_benchmark^2)
    systematic_underfunding_score = ss_under / ss_all

This ratio measures what fraction of the plan's total benchmark deviation is attributable to underfunding (falling below peer average) rather than overfunding (exceeding it). A score near 1.0 indicates that the plan is consistently and strongly underfunded relative to peers; a score near 0 indicates the plan's deviations are roughly balanced between under and over. This metric surfaces crises that are systematically neglected compared to similar emergencies in the same year, even if the absolute funding ratio appears reasonable in isolation. The assessment module uses this score to identify crises where historical underperformance relative to peer funding is a key risk driver.

Sector and needs pressure come from category-level severity values held in `crisis["category_scores"]`. These scores are computed by the data pipeline in the `build_category_scores()` function from a category breakdown array. Each category has an estimated number of people `in_need` and a number of people `targeted` by interventions. For each category, the coverage is computed as:

    coverage = min(targeted / in_need, 1.0)
    gap = 1.0 - coverage

The gap for each category is then normalized by its weight in the total need. Specifically, if the total people in need across all categories is `total_in_need`, then:

    weight = in_need / total_in_need
    category_score = weight * gap

All category scores are summed to produce the sector-level gap aggregate. The assessment extracts metrics such as the maximum category score, average category score, and counts of categories where the score exceeds thresholds (e.g., >= 80 for high, >= 90 for severe). These values indicate the breadth and intensity of sectoral deprivation and are interpreted as sector pressure indicators within the assessment logic.

Temporal signals are inferred from funding timeline history. The assessment summarizes the last few years of funding coverage into a trend label: `declining`, `flat`, or `improving`. It also compares the latest year to the peer benchmark and sets boolean signals when the latest coverage is significantly below or at/above the peer average.

Requirement dynamics are also tracked. If reported requirements are rising by 10% or more year-over-year, or if there is sustained upward demand over multiple years, the assessment marks the crisis as having worsening demand.

The final assessment band is chosen using a cascade of logical conditions.

- `Critically Underfunded` is selected when the crisis has an acute underfunding signal and either structural scale pressure or high underfunding intensity.
- `Significantly Underfunded` is selected when there is an acute underfunding signal but without the highest structural severity.
- `Likely Underfunded` is selected when there are weaker underfunding signals.
- `Adequately Supported` is selected when the funding ratio is high, the trend is stable or improving, the latest position is at or above peer benchmark, and sector/systematic risks are low or missing.
- `Some Funding Gaps` is the default fallback.

This band is converted into a numeric rank using `ASSESSMENT_RANKS` in `dashboard/main.py`, and the dashboard uses that rank for default sorting.

The system explicitly handles missing or inconsistent data. If the funding ratio is unavailable, the logic still produces an assessment and adds a rationale like "Funding ratio data incomplete". If requirements are missing or projected, it adds a "Data-limited assessment" driver. If category breakdown or systematic benchmark data are absent, the assessment continues using the remaining available signals.

The core implementation is heuristic rather than model-based. It uses thresholded boolean rules, confidence-weighted rationale selection, and simple trend inference. The only external API interaction in the repo is the LLM summary generator in `dashboard/llm_summary.py`, which uses Anthropic's Claude 3 Haiku model (claude-3-haiku-20240307). The system loads an `ANTHROPIC_API_KEY` from environment variables. When a crisis is loaded, the generator creates an asynchronous prompt that includes the full crisis dictionary as JSON, asks the model to explain why the crisis has its assigned `overall_severity_score`, and constrains the response to 2-3 sentences with a system prompt identifying the model as an expert humanitarian crisis analyst. The model response is limited to 300 tokens. Results are cached in `crisis_summaries_cache.json` with SHA256 checksums of the source data file to detect staleness. If no API key is configured or if the async call fails, the system gracefully returns a fallback string without crashing the ranking. This LLM component is used only for narrative text generation and not for numeric ranking or assessment logic.

Principal limitations of this design include the brittleness of fixed thresholds, sensitivity to incomplete or stale data, and the limited temporal modeling in the trend signal. The benchmark-based score depends on proper historical plan matching, and mismatches there can distort the `systematic_underfunding_score`. The moderation of evidence also means only the top three rationale drivers are surfaced, which can omit important secondary signals. Most critically, the current system relies entirely on quantitative funding and need metrics. The humanitarian response data available lacks rich qualitative context: project descriptions, implementation challenges, geographic access constraints, conflict-related impediments, and contextual narratives are largely absent from the FTS and HNO datasets.

To extend the assessment with temporal and cross-source signals, the system should incorporate multi-year momentum metrics, stronger cross-source consistency checks, and explicit data-quality scoring. A more advanced version would combine sector gap, funding ratio gap, benchmark underperformance, demand growth, and external risk signals into a unified mismatch score. It would be valuable to add explicit provenance flags for stale or projected requirements and to train a weighted ranking model on historical outcomes or expert labels.

However, the most impactful improvements would emerge from richer data. If project-level descriptions, implementation barriers, local context summaries, and operational constraints were available in the source data, the assessment could move beyond numeric gap analysis. Such qualitative inputs could be aggregated at the crisis level and ingested directly into the LLM prompt, allowing the Claude summarizer to produce explanations grounded in both quantitative mismatch signals and real operational realities. For instance, a crisis showing low funding but high peer-benchmark performance might appear adequately supported numerically but could reveal itself as critically underfunded once qualitative data reveals systematic access barriers or displacement dynamics. Conversely, high funding might mask inefficiency if projects lack clear implementation pathways. Enriching the data pipeline with these qualitative signals—even as structured categories or short text fields—would transform the assessment from a purely financial gap model into one that reflects the actual humanitarian landscape.
