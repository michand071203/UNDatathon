import argparse
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
FTS_FILE = DATA_DIR / "fts_requirements_funding_global.csv"

MONTHS_PATTERN = (
    r"january|february|march|april|may|june|july|august|"
    r"september|october|november|december"
)


@dataclass
class Candidate:
    kind: str
    key: str
    base_keys: list[str]
    latest_year: int | None
    latest_base_keys: list[str]
    countries: list[str]
    sample_names: list[str]


def strip_year_suffix(code: str, year: float) -> str:
    if not isinstance(code, str) or not code:
        return ""
    if pd.isna(year):
        return code

    yy = int(year) % 100
    token = f"{yy:02d}"
    return re.sub(rf"{token}(?=[A-Za-z]?$)", "", code)


def normalize_name(name: str) -> str:
    text = str(name or "").lower()
    text = re.sub(r"\b(19|20)\d{2}\b", " ", text)
    text = re.sub(rf"\b({MONTHS_PATTERN})\b", " ", text)
    text = re.sub(r"\b\d+\b", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def build_exact_candidates(df: pd.DataFrame) -> list[Candidate]:
    candidates: list[Candidate] = []

    grouped = df.groupby("name_norm", dropna=False)
    for name_norm, group in grouped:
        bases = sorted(set(group["base_key"].dropna().tolist()))
        if len(bases) <= 1:
            continue

        latest_year = int(group["year"].max()) if not group["year"].isna().all() else None
        latest_base_keys = (
            sorted(set(group.loc[group["year"] == latest_year, "base_key"].dropna().tolist()))
            if latest_year is not None
            else []
        )
        countries = sorted(set(group["countryCode"].dropna().astype(str).str.upper().tolist()))
        sample_names = sorted(set(group["name"].dropna().astype(str).tolist()))[:3]

        candidates.append(
            Candidate(
                kind="exact",
                key=name_norm,
                base_keys=bases,
                latest_year=latest_year,
                latest_base_keys=latest_base_keys,
                countries=countries,
                sample_names=sample_names,
            )
        )

    return candidates


def build_similar_candidates(
    df: pd.DataFrame,
    similarity_threshold: float,
    min_token_overlap: int,
) -> list[Candidate]:
    candidates: list[Candidate] = []

    name_groups = (
        df.groupby("name_norm", dropna=False)
        .agg(
            base_keys=("base_key", lambda s: sorted(set(s.dropna().tolist()))),
            latest_year=("year", "max"),
            countries=(
                "countryCode",
                lambda s: sorted(set(s.dropna().astype(str).str.upper().tolist())),
            ),
            sample_names=("name", lambda s: sorted(set(s.dropna().astype(str).tolist()))[:2]),
        )
        .reset_index()
    )

    rows = name_groups.to_dict("records")
    used_pairs: set[tuple[str, str]] = set()

    for i in range(len(rows)):
        a = rows[i]
        a_norm = a["name_norm"]
        if not a_norm:
            continue
        a_tokens = set(a_norm.split())

        for j in range(i + 1, len(rows)):
            b = rows[j]
            b_norm = b["name_norm"]
            if not b_norm:
                continue

            pair_key = tuple(sorted((a_norm, b_norm)))
            if pair_key in used_pairs:
                continue

            b_tokens = set(b_norm.split())
            overlap = len(a_tokens & b_tokens)
            if overlap < min_token_overlap:
                continue

            ratio = SequenceMatcher(None, a_norm, b_norm).ratio()
            if ratio < similarity_threshold:
                continue

            merged_bases = sorted(set(a["base_keys"] + b["base_keys"]))
            if len(merged_bases) <= max(len(a["base_keys"]), len(b["base_keys"])):
                continue

            latest_year = int(max(a["latest_year"], b["latest_year"]))
            latest_base_keys = sorted(
                set(
                    (a["base_keys"] if int(a["latest_year"]) == latest_year else [])
                    + (b["base_keys"] if int(b["latest_year"]) == latest_year else [])
                )
            )

            merged_countries = sorted(set(a["countries"] + b["countries"]))
            merged_names = sorted(set(a["sample_names"] + b["sample_names"]))[:4]

            candidates.append(
                Candidate(
                    kind="similar",
                    key=f"{a_norm}  <~>  {b_norm}",
                    base_keys=merged_bases,
                    latest_year=latest_year,
                    latest_base_keys=latest_base_keys,
                    countries=merged_countries,
                    sample_names=merged_names,
                )
            )
            used_pairs.add(pair_key)

    return candidates


def print_candidates(candidates: list[Candidate], limit: int) -> None:
    if not candidates:
        print("No candidate stitch groups found.")
        return

    def score(c: Candidate) -> tuple[int, int]:
        return (len(c.base_keys), len(c.countries))

    ranked = sorted(candidates, key=score, reverse=True)[:limit]

    for idx, c in enumerate(ranked, start=1):
        print(f"\n[{idx}] kind={c.kind}")
        print(f"name_key: {c.key}")
        print(f"base_keys ({len(c.base_keys)}): {c.base_keys}")
        print(f"latest_year: {c.latest_year}")
        print(f"latest_base_keys: {c.latest_base_keys}")
        print(f"countries ({len(c.countries)}): {c.countries}")
        print(f"sample_names: {c.sample_names}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Find candidate FTS base-key stitch families by exact and similar plan names."
    )
    parser.add_argument(
        "--keywords",
        default="refugee,rrp,regional refugee,migrant response plan,resilience plan",
        help="Comma-separated lowercase keywords to filter plan names before analysis.",
    )
    parser.add_argument(
        "--similarity-threshold",
        type=float,
        default=0.9,
        help="Minimum SequenceMatcher ratio for similar-name candidate detection.",
    )
    parser.add_argument(
        "--min-token-overlap",
        type=int,
        default=3,
        help="Minimum shared token count required before fuzzy comparison.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=30,
        help="Maximum candidates to print per section.",
    )
    args = parser.parse_args()

    if not FTS_FILE.exists():
        raise FileNotFoundError(f"Missing input file: {FTS_FILE}")

    df = pd.read_csv(FTS_FILE, comment="#")
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df = df[df["code"].notna() & df["year"].notna()].copy()

    df["base_key"] = [strip_year_suffix(c, y) for c, y in zip(df["code"], df["year"])]
    df["name_norm"] = df["name"].map(normalize_name)

    keywords = [k.strip().lower() for k in args.keywords.split(",") if k.strip()]
    if keywords:
        mask = df["name"].astype(str).str.lower().apply(
            lambda text: any(k in text for k in keywords)
        )
        df = df[mask].copy()

    print(f"Input rows after filtering: {len(df)}")
    print(f"Unique normalized names: {df['name_norm'].nunique()}")

    exact_candidates = build_exact_candidates(df)
    similar_candidates = build_similar_candidates(
        df,
        similarity_threshold=args.similarity_threshold,
        min_token_overlap=args.min_token_overlap,
    )

    print("\n=== Exact-name stitch candidates ===")
    print_candidates(exact_candidates, limit=args.limit)

    print("\n=== Similar-name stitch candidates ===")
    print_candidates(similar_candidates, limit=args.limit)


if __name__ == "__main__":
    main()
