import random

MOCK_DATA = {
    "BOM": {
        "12w": {"DXB": 0.86, "LHR": 0.96, "SIN": 0.98, "BKK": 0.92},
        "8w": {"DXB": 0.92, "LHR": 0.94, "SIN": 0.90, "BKK": 0.82},
        "2w": {"DXB": 0.98, "LHR": 0.96, "SIN": 0.84, "BKK": 0.94}
    },
    "DEL": {
        "12w": {"JFK": 0.78, "LHR": 0.86, "DXB": 0.88},
        "8w": {"JFK": 0.88, "LHR": 0.88, "DXB": 0.86},
        "2w": {"JFK": 0.96, "LHR": 0.90, "DXB": 0.86}
    },
    "BLR": {
        "12w": {"DOH": 0.72, "FRA": 0.70, "SFO": 0.80},
        "8w": {"DOH": 0.86, "FRA": 0.80, "SFO": 0.82},
        "2w": {"DOH": 0.94, "FRA": 0.88, "SFO": 0.86}
    },
    "MAA": {
        "12w": {"SIN": 0.90, "KUL": 0.86, "DXB": 0.84},
        "8w": {"SIN": 0.92, "KUL": 0.88, "DXB": 0.82},
        "2w": {"SIN": 0.94, "KUL": 0.90, "DXB": 0.80}
    },
    "HYD": {
        "12w": {"DXB": 0.88, "DOH": 0.80, "LHR": 0.76},
        "8w": {"DXB": 0.90, "DOH": 0.84, "LHR": 0.78},
        "2w": {"DXB": 0.92, "DOH": 0.88, "LHR": 0.80}
    }
}

extra_dests = ["AMS", "SYD", "MEL", "BNE", "PER", "AKL", "HKG", "NRT", "HND", "ICN", "TPE", "MNL", "CGK", "SGN", "CDG", "YYZ", "ORD", "JED", "CMB"]
random.seed(42)

for origin in MOCK_DATA:
    for snapshot in ["2w", "8w", "12w"]:
        current_dests = list(MOCK_DATA[origin][snapshot].keys())
        needed = 20 - len(current_dests)
        for d in random.sample(extra_dests, needed):
            MOCK_DATA[origin][snapshot][d] = round(random.uniform(0.1, 0.6), 2)

def get_mock_snapshots(origin: str) -> dict:
    if origin not in MOCK_DATA:
        raise ValueError(f"Origin {origin} not found in mock data")
    return {"origin": origin, "snapshots": MOCK_DATA[origin]}
