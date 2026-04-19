import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Optional


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR.parent / "data"
INPUT_FILE = DATA_DIR / "hpc_hno_2026.csv"
OUTPUT_FILE = BASE_DIR / "hno_all.json"


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
    except Exception:
        return None


def row_to_record(row: Dict[str, str]) -> Dict[str, Any]:
    # Keep original keys but coerce obvious numeric columns used in HNO
    return {
        "Country ISO3": clean_string(row.get("Country ISO3")),
        "Description": clean_string(row.get("Description")),
        "Population": parse_int(row.get("Population")),
        "In Need": parse_int(row.get("In Need")),
        "Targeted": parse_int(row.get("Targeted")),
    }


def main() -> None:
    if not INPUT_FILE.exists():
        print(f"Input file not found: {INPUT_FILE}")
        return

    with INPUT_FILE.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        all_rows: List[Dict[str, Any]] = []
        for row in reader:
            cluster = clean_string(row.get("Cluster")) or ""
            if cluster.upper() != "ALL":
                continue
            all_rows.append(row_to_record(row))

    OUTPUT_FILE.write_text(json.dumps(all_rows, indent=2, ensure_ascii=False) + "\n")
    print(f"Wrote {len(all_rows)} ALL rows to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
