# Michal Exploration

This folder contains a normalized JSON aggregation of the humanitarian CSV inputs in `/data`.

## Files

- `build_aggregated_crisis_json.py`: builds the aggregated artifact and validation report.
- `aggregated_crisis_data.json`: country-centered normalized JSON output.
- `aggregation_report.json`: validation and data-quality notes for the generated artifact.

## Design

The output is intentionally **country-centered** because:

- `hpc_hno_2026.csv` is the cleanest country-level source of humanitarian need.
- sector-level detail can be nested below each country without distorting national totals.
- plan-level funding can be attached as sub-objects instead of forcing an unstable flat join.

## Main assumptions

- Country-level need uses the `Cluster = ALL` HNO row when present.
- HNO sector rows are preserved under `hno_sectors` and are **not** summed into the country total.
- FTS rows with blank `code` values are treated as unattributed country-level funding and excluded from `primary_plan_2026`.
- FTS history is limited to years up to `2026` so the artifact does not mix historical analysis with future placeholder rows.
- CBPF allocation and contribution summary CSVs are kept in `global_summaries` because their visible schema does not expose a reliable country join key.
- `2026_crisis_summary.csv` is not used as an input because it is already a derived output.

## Run

```bash
python3 /Users/michalandrzejewski/Desktop/Projects_Eth/Datathon/UNDatathon/michal_exploration/build_aggregated_crisis_json.py
```

## Output structure

- `meta`: provenance, scope, and source-file notes.
- `global_summaries`: global CBPF summaries that do not safely join at country level.
- `countries`: one object per HNO crisis country.

Each country includes:

- `reference`: HNO and COD population references.
- `hno`: country-level humanitarian need.
- `hno_sectors`: sector need detail.
- `hrp_2026`: cleaned HRP metadata rows that reference the country.
- `fts_plans_2026`: 2026 FTS plans with valid plan codes.
- `primary_plan_2026`: selected primary plan for downstream ranking.
- `flow_summaries_by_plan_2026`: incoming, outgoing, and internal flow summaries for every valid 2026 FTS plan attached to the country.
- `funding_flows_2026`: incoming, outgoing, and internal flow summaries for the selected plan.
- `sector_funding_2026`: both normalized and raw FTS cluster funding views.
- `history`: multi-year FTS country totals plus unattributed funding.
