from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
CSV_FILE = BASE_DIR / "data" / "2026_crisis_summary.csv"
JSON_FILE = BASE_DIR / "2026_crisis_summary.json"


def main():
    if not CSV_FILE.exists():
        print(f"Error: {CSV_FILE} not found.")
        return

    df = pd.read_csv(CSV_FILE)

    # Convert to JSON with records orientation (list of dicts)
    json_data = df.to_json(orient="records", indent=2)

    with open(JSON_FILE, "w") as f:
        f.write(json_data)

    print(f"Converted {CSV_FILE} to {JSON_FILE}")


if __name__ == "__main__":
    main()
