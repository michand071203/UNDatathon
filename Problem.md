# Geo-Insight: Which Crises Are Most Overlooked?

## Overview
In this challenge, you will build a system that surfaces mismatches between humanitarian need and humanitarian financing coverage across active crises worldwide.

Your task is to take a crisis context, a geographic scope, or a natural-language query and return the situations that are most underserved, ranked by the gap between actual need and available funding.

This challenge is based on a real analytical problem inside the humanitarian data ecosystem. Humanitarian coordinators and donor advisors need to quickly identify where funds are not reaching, relative to the scale of a crisis.

## The Problem
Humanitarian data mixes two very different kinds of signals:

- Objective severity indicators that describe the scale and urgency of a crisis.
- Funding and coverage data that describes what has actually been resourced.

Example questions a decision-maker might ask:

- "Which crises have the highest proportion of people in need but the lowest fund allocations?"
- "Are there countries with active HRPs where funding is absent or negligible?"
- "Which regions are consistently underfunded relative to need across multiple years?"
- "Show me acute food insecurity hotspots that have received less than 10% of their requested funding."

In all four examples, some signals are objective thresholds and some are relative or contextual judgments. Your system should separate these layers and combine them effectively.

## Core Task
Given a query or geographic scope:

1. Identify relevant crises or countries using severity and needs data.
2. Filter to situations meeting a meaningful threshold of documented need.
3. Interpret funding coverage data to compute a gap or mismatch score.
4. Rank the crises by how overlooked they appear, relative to need.

Your result should ideally support:

- A ranked list of crises or countries with a gap score or coverage ratio.
- Map-ready outputs using country or crisis coordinates where available.
- A short explanation of why the top results rank as most overlooked.

Assume you only have publicly available datasets and the current query or scope provided.

## Bonus Task
Use temporal or cross-source signals to improve ranking and identify structural neglect rather than just point-in-time gaps.

Examples of additional signals:

- Multi-year funding trends for the same crisis.
- HRP target vs. actual coverage over time.
- Whether a crisis appears in global media or advocacy reporting.
- Population displacement or IDP figures as a need multiplier.
- Sector-level gaps within a crisis (e.g., health vs. food vs. shelter).
- Donor concentration, where a crisis relies on one or two major donors.

**Bonus question:** How should ranking change when a crisis has been underfunded for multiple consecutive years versus one that is newly underfunded? How can you represent structural issues differently from acute emergencies?

## Directions You Can Explore
You are free to choose different solution styles as long as the core task is addressed and the final outcome is strong.

Possible directions include:

- A gap-scoring pipeline using HNO and funding data only.
- A retrieval system over crisis summaries and metadata.
- An LLM-assisted query understanding layer that maps natural-language questions to filter criteria.
- A hybrid approach combining structured funding ratios with semantic scoring over crisis descriptions.
- Geospatial analysis using country centroids or crisis coordinates.
- Enrichment using external data such as ACLED conflict events, IPC food security phases, or UNHCR displacement figures.
- Time-series analysis of funding trends per crisis.
- A lightweight visualization or dashboard.
- A conversational interface where a user can refine scope across multiple turns.

Everything that helps answer the core question of where need outpaces coverage is encouraged.
