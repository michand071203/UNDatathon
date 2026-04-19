# Underfunding Assessment Writeup

## 1. What the underfunding assessment does

- `dashboard/underfunding_assessment.py` converts crisis metrics into:
  - a discrete assessment band
  - a ranked list of up to 3 rationale drivers
  - evidence confidence for each driver
- The dashboard then uses this band via `ASSESSMENT_RANKS` in `dashboard/main.py` to order results by severity.

## 2. Gap and mismatch scoring logic

The assessment combines several gap-related signals:

- `funding_ratio_value`
  - Derived from `crisis["percent_funded"]`
  - Critical thresholds:
    - `< 5%` extreme
    - `< 10%` critical
    - `< 25%` low
    - `>= 45%` strong
    - `>= 80%` adequate

- `funding_gap`
  - If both `requirements` and `funding` exist, it is:
    - `max(requirements - funding, 0)`
  - This is used as an absolute pressure signal rather than a normalized score.

- `systematic_underfunding_score`
  - Uses historical benchmark comparison from pipeline data
  - Derived from the ratio of weighted squared underfunding gaps to total benchmark variance:
    - `eta_sq = ss_under / ss_all`
    - Where `ss_under` is weighted `underfunding_gap^2`
    - and `ss_all` is weighted `gap_vs_benchmark^2`
  - It identifies whether a crisis is persistently below peer-average funding performance.

- Sector/needs pressure
  - Uses category score summaries from `crisis["category_scores"]`
  - Determines:
    - `category_max`
    - `category_avg`
    - counts of high/severe sector gap values

- Trend signals
  - Uses funding timeline history to infer:
    - `declining`, `flat`, or `improving`
  - Also compares latest funding ratio to peer average:
    - `latest_below_peer`
    - `latest_at_or_above_peer`

- Requirements dynamics
  - Looks for worsening demand if recent requirement growth is >= 10% YoY or sustained increases

## 3. Final assessment / ranking logic

The band is selected by a cascade of signals:

- `Critically Underfunded`
  - if acute underfunding signals exist AND either:
    - structural scale pressure or
    - high underfunding intensity

- `Significantly Underfunded`
  - if acute underfunding signals exist without the extra structural severity

- `Likely Underfunded`
  - if weaker underfunding signals are present

- `Adequately Supported`
  - if high funding ratio, stable or improving trend, peer benchmark at/above average,
    and low/missing sector or systematic risk

- `Some Funding Gaps`
  - default fallback when the above criteria are not met

This means the dashboard ranks crises by `assessment_rank`, where more severe bands are ordered higher.

## 4. Handling missing, outdated, or inconsistent data

- Missing funding ratio
  - yields the rationale `"Funding ratio data incomplete"` with moderate confidence
- Missing requirements or projected data
  - produces a `"Data-limited assessment"` signal
- Missing systematic underfunding
  - still allows assessment using funding ratio, trend, category, and gap signals
- Missing category data
  - results in weaker sector signals but does not block an assessment
- Trend summaries ignore invalid or incomplete year points
  - they only use valid numeric years and funding ratios

## 5. Heuristics and external systems used

- Core logic is heuristic, not ML:
  - threshold-based branches
  - boolean signal combinations
  - confidence weights for rationale selection
- The only external system in the repo is the optional LLM summarizer:
  - `dashboard/llm_summary.py` uses Anthropic Claude for crisis summaries
  - This is separate from the assessment ranking itself

## 6. Failure cases and limitations

- **Heuristic thresholds are brittle**
  - fixed cutoffs can misclassify crises near boundaries
- **Data quality dependency**
  - incomplete or stale `percent_funded`, `requirements`, or sector breakdowns weaken the signal
- **Historical benchmark risk**
  - if historical plan grouping is wrong, `systematic_underfunding_score` may be misleading
- **Limited temporal modeling**
  - trend detection is simple delta-based, not a true time-series model
- **Mixed evidence handling**
  - the system chooses up to 3 drivers, but it may drop relevant secondary signals
- **No uncertainty quantification**
  - confidence is heuristic rather than statistically calibrated

## 7. How to extend this for temporal / cross-source bonus signals

- Add multi-year momentum metrics
  - moving averages, acceleration, and persistence of funding gaps
- Use cross-source consistency
  - compare FTS plan funding to cluster/global funding, incoming/outgoing flows, and external risk indices
- Introduce a learned ranking model
  - train weights on historical crisis outcomes or expert labels
- Add data-quality signals
  - flag stale or projected requirements explicitly in scoring
- Build a combined mismatch score
  - unify:
    - sector gap
    - funding ratio gap
    - benchmark underperformance
    - demand growth
    - external risk signals

- Add explicit data-quality provenance and stale-data flags to make ranking more robust.
