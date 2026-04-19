import csv
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
MD_FILE = DATA_DIR / "2026_crisis_rankings_table.md"
CSV_FILE = DATA_DIR / "2026_crisis_rankings_table.csv"


def parse_markdown_table(md_content):
    lines = md_content.strip().split("\n")
    # Skip the title and header separator
    data_lines = [
        line
        for line in lines
        if line.startswith("|")
        and not line.startswith("| ---")
        and not line.startswith("|-------------")
    ]

    # Extract header
    header_line = data_lines[0]
    headers = [col.strip() for col in header_line.split("|")[1:-1]]

    # Extract data rows
    data_rows = []
    for line in data_lines[1:]:
        cols = [col.strip() for col in line.split("|")[1:-1]]
        data_rows.append(cols)

    return headers, data_rows


def main():
    with open(MD_FILE, "r", encoding="utf-8") as f:
        md_content = f.read()

    headers, data_rows = parse_markdown_table(md_content)

    with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(data_rows)

    print(f"CSV file saved to {CSV_FILE}")


if __name__ == "__main__":
    main()
