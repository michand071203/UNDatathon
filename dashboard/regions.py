from typing import List, Set, Tuple


REGION_TO_ISO3 = {
    "africa": [
        "DZA", "AGO", "BEN", "BWA", "BFA", "BDI", "CMR", "CPV", "CAF", "TCD", "COM", "COG", "COD", "CIV", "DJI", "EGY", "GNQ", "ERI", "SWZ", "ETH", "GAB", "GMB", "GHA", "GIN", "GNB", "KEN", "LSO", "LBR", "LBY", "MDG", "MWI", "MLI", "MRT", "MUS", "MAR", "MOZ", "NAM", "NER", "NGA", "RWA", "STP", "SEN", "SYC", "SLE", "SOM", "ZAF", "SSD", "SDN", "TZA", "TGO", "TUN", "UGA", "ZMB", "ZWE"
    ],
    "north africa": ["DZA", "EGY", "LBY", "MAR", "SDN", "TUN"],
    "sub-saharan africa": [
        "AGO", "BEN", "BWA", "BFA", "BDI", "CMR", "CPV", "CAF", "TCD", "COM", "COG", "COD", "CIV", "DJI", "GNQ", "ERI", "SWZ", "ETH", "GAB", "GMB", "GHA", "GIN", "GNB", "KEN", "LSO", "LBR", "MDG", "MWI", "MLI", "MRT", "MUS", "MOZ", "NAM", "NER", "NGA", "RWA", "STP", "SEN", "SYC", "SLE", "SOM", "ZAF", "SSD", "TZA", "TGO", "UGA", "ZMB", "ZWE"
    ],
    "west africa": ["BEN", "BFA", "CPV", "CIV", "GMB", "GHA", "GIN", "GNB", "LBR", "MLI", "MRT", "NER", "NGA", "SEN", "SLE", "TGO"],
    "east africa": ["BDI", "COM", "DJI", "ERI", "ETH", "KEN", "RWA", "SOM", "SSD", "SDN", "TZA", "UGA"],
    "central africa": ["CMR", "CAF", "TCD", "COG", "COD", "GNQ", "GAB"],
    "southern africa": ["AGO", "BWA", "SWZ", "LSO", "MDG", "MWI", "MUS", "MOZ", "NAM", "ZAF", "ZMB", "ZWE"],
    "middle east": ["BHR", "IRN", "IRQ", "ISR", "JOR", "KWT", "LBN", "OMN", "PSE", "QAT", "SAU", "SYR", "TUR", "ARE", "YEM"],
    "mena": ["DZA", "BHR", "DJI", "EGY", "IRN", "IRQ", "ISR", "JOR", "KWT", "LBN", "LBY", "MAR", "OMN", "PSE", "QAT", "SAU", "SDN", "SYR", "TUN", "TUR", "ARE", "YEM"],
    "asia": [
        "AFG", "ARM", "AZE", "BHR", "BGD", "BTN", "BRN", "KHM", "CHN", "GEO", "IND", "IDN", "IRN", "IRQ", "ISR", "JPN", "JOR", "KAZ", "KWT", "KGZ", "LAO", "LBN", "MYS", "MDV", "MNG", "MMR", "NPL", "PRK", "OMN", "PAK", "PSE", "PHL", "QAT", "SAU", "SGP", "KOR", "LKA", "SYR", "TWN", "TJK", "THA", "TLS", "TUR", "TKM", "ARE", "UZB", "VNM", "YEM"
    ],
    "south asia": ["AFG", "BGD", "BTN", "IND", "MDV", "NPL", "PAK", "LKA"],
    "southeast asia": ["BRN", "KHM", "IDN", "LAO", "MYS", "MMR", "PHL", "SGP", "THA", "TLS", "VNM"],
    "central asia": ["KAZ", "KGZ", "TJK", "TKM", "UZB"],
    "europe": [
        "ALB", "AND", "AUT", "BEL", "BIH", "BGR", "HRV", "CYP", "CZE", "DNK", "EST", "FIN", "FRA", "DEU", "GRC", "HUN", "ISL", "IRL", "ITA", "LVA", "LIE", "LTU", "LUX", "MLT", "MDA", "MCO", "MNE", "NLD", "MKD", "NOR", "POL", "PRT", "ROU", "SMR", "SRB", "SVK", "SVN", "ESP", "SWE", "CHE", "UKR", "GBR", "VAT"
    ],
    "eastern europe": ["BLR", "BGR", "CZE", "HUN", "MDA", "POL", "ROU", "RUS", "SVK", "UKR"],
    "americas": [
        "ATG", "ARG", "BHS", "BRB", "BLZ", "BOL", "BRA", "CAN", "CHL", "COL", "CRI", "CUB", "DMA", "DOM", "ECU", "SLV", "GRD", "GTM", "GUY", "HTI", "HND", "JAM", "MEX", "NIC", "PAN", "PRY", "PER", "KNA", "LCA", "VCT", "SUR", "TTO", "USA", "URY", "VEN"
    ],
    "north america": ["CAN", "MEX", "USA"],
    "latin america": ["ARG", "BOL", "BRA", "CHL", "COL", "CRI", "CUB", "DOM", "ECU", "SLV", "GTM", "GUY", "HTI", "HND", "JAM", "NIC", "PAN", "PRY", "PER", "SUR", "URY", "VEN"],
    "caribbean": ["ATG", "BHS", "BRB", "CUB", "DMA", "DOM", "GRD", "HTI", "JAM", "KNA", "LCA", "VCT", "TTO"],
    "oceania": ["AUS", "FJI", "KIR", "MHL", "FSM", "NRU", "NZL", "PLW", "PNG", "WSM", "SLB", "TON", "TUV", "VUT"],
    "pacific": ["FJI", "KIR", "MHL", "FSM", "NRU", "PLW", "PNG", "WSM", "SLB", "TON", "TUV", "VUT"],
}

REGION_ALIASES = {
    "middle east and north africa": "mena",
    "m.e.": "middle east",
    "east asia": "asia",
    "south east asia": "southeast asia",
    "sub saharan africa": "sub-saharan africa",
    "subsaharan africa": "sub-saharan africa",
}

REGION_NAMES: Tuple[str, ...] = tuple(REGION_TO_ISO3.keys())


def canonical_region_name(location_value: str) -> str:
    normalized = " ".join(location_value.strip().lower().split())
    return REGION_ALIASES.get(normalized, normalized)


def expand_location_values(values: List[str], available_iso3: Set[str]) -> List[str]:
    expanded: List[str] = []
    for value in values:
        token = str(value).strip()
        if not token:
            continue

        upper_token = token.upper()
        if upper_token in available_iso3:
            expanded.append(upper_token)
            continue

        canonical = canonical_region_name(token)
        region_codes = REGION_TO_ISO3.get(canonical)
        if region_codes:
            expanded.extend(code for code in region_codes if code in available_iso3)
            continue

        expanded.append(token)

    seen = set()
    deduped: List[str] = []
    for item in expanded:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped