SEED_DATA = {
    "airports": [
        {"code": "BOM", "name": "Mumbai Chhatrapati Shivaji Maharaj", "lat": 19.0896, "lon": 72.8656},
        {"code": "DEL", "name": "Delhi Indira Gandhi International", "lat": 28.5562, "lon": 77.1000},
        {"code": "BLR", "name": "Bengaluru Kempegowda", "lat": 13.1986, "lon": 77.7066},
        {"code": "MAA", "name": "Chennai International", "lat": 12.9941, "lon": 80.1709},
        {"code": "HYD", "name": "Hyderabad Rajiv Gandhi", "lat": 17.2403, "lon": 78.4294},
        {"code": "DXB", "name": "Dubai International", "lat": 25.2532, "lon": 55.3657},
        {"code": "SIN", "name": "Singapore Changi", "lat": 1.3644, "lon": 103.9915},
        {"code": "LHR", "name": "London Heathrow", "lat": 51.4700, "lon": -0.4543},
        {"code": "JFK", "name": "New York JFK", "lat": 40.6413, "lon": -73.7781},
        {"code": "CDG", "name": "Paris Charles de Gaulle", "lat": 49.0097, "lon": 2.5479},
        {"code": "NRT", "name": "Tokyo Narita", "lat": 35.7647, "lon": 140.3863},
        {"code": "BKK", "name": "Bangkok Suvarnabhumi", "lat": 13.6900, "lon": 100.7501},
        {"code": "KUL", "name": "Kuala Lumpur International", "lat": 2.7456, "lon": 101.7099},
        {"code": "DOH", "name": "Doha Hamad International", "lat": 25.2730, "lon": 51.6080},
        {"code": "SYD", "name": "Sydney Kingsford Smith", "lat": -33.9399, "lon": 151.1753}
    ],
    "airlines": [
        {"code": "AI", "name": "Air India", "alliance": "Star Alliance"},
        {"code": "EK", "name": "Emirates", "alliance": "None"},
        {"code": "QR", "name": "Qatar Airways", "alliance": "Oneworld"},
        {"code": "SQ", "name": "Singapore Airlines", "alliance": "Star Alliance"},
        {"code": "BA", "name": "British Airways", "alliance": "Oneworld"},
        {"code": "6E", "name": "IndiGo", "alliance": "None"}
    ],
    "routes": [
        {"origin": "BOM", "destination": "DXB", "airlines": ["AI", "EK"], "distance_km": 1930},
        {"origin": "BOM", "destination": "LHR", "airlines": ["AI", "BA"], "distance_km": 7200},
        {"origin": "BOM", "destination": "SIN", "airlines": ["AI", "SQ", "6E"], "distance_km": 3900},
        {"origin": "BOM", "destination": "JFK", "airlines": ["AI"], "distance_km": 12500},
        {"origin": "BOM", "destination": "DOH", "airlines": ["QR"], "distance_km": 2300},
        {"origin": "BOM", "destination": "BKK", "airlines": ["AI"], "distance_km": 3000},
        {"origin": "DEL", "destination": "DXB", "airlines": ["AI", "EK"], "distance_km": 2200},
        {"origin": "DEL", "destination": "LHR", "airlines": ["AI", "BA"], "distance_km": 6700},
        {"origin": "DEL", "destination": "JFK", "airlines": ["AI"], "distance_km": 11750},
        {"origin": "DEL", "destination": "SIN", "airlines": ["AI", "SQ"], "distance_km": 4150},
        {"origin": "DEL", "destination": "CDG", "airlines": ["AI"], "distance_km": 6600},
        {"origin": "BLR", "destination": "DXB", "airlines": ["AI", "EK"], "distance_km": 2700},
        {"origin": "BLR", "destination": "SIN", "airlines": ["SQ"], "distance_km": 3150},
        {"origin": "BLR", "destination": "BKK", "airlines": ["AI"], "distance_km": 2450},
        {"origin": "MAA", "destination": "SIN", "airlines": ["SQ"], "distance_km": 2900},
        {"origin": "MAA", "destination": "KUL", "airlines": ["AI"], "distance_km": 2600},
        {"origin": "HYD", "destination": "DXB", "airlines": ["EK"], "distance_km": 2550},
        {"origin": "HYD", "destination": "SIN", "airlines": ["SQ"], "distance_km": 3300},
        {"origin": "BOM", "destination": "NRT", "airlines": ["AI"], "distance_km": 6800},
        {"origin": "DEL", "destination": "SYD", "airlines": ["AI"], "distance_km": 10400}
    ],
    "fare_classes": [
        {"code": "Y", "name": "Full Economy", "change_fee_inr": 8000, "refund_pct": 75, "description": "Highly flexible economy fare class. Changeable for an INR 8,000 fee. Refundable with 75% returned on cancellation."},
        {"code": "M", "name": "Semi-restricted economy", "change_fee_inr": 5000, "refund_pct": 50, "description": "Semi-flexible economy fare. Changeable for an INR 5,000 fee. 50% refund on cancellations. Moderate restrictions apply."},
        {"code": "K", "name": "Restricted economy", "change_fee_inr": 3000, "refund_pct": 0, "description": "Restricted economy fare class. Changeable for INR 3,000. Absolutely non-refundable on cancellation."},
        {"code": "Q", "name": "Deep discount", "change_fee_inr": 999999, "refund_pct": 0, "description": "Deep discount promotional fare. Completely non-changeable and non-refundable. Seat selection and luggage may have extra fees."},
        {"code": "J", "name": "Full Business", "change_fee_inr": 0, "refund_pct": 100, "description": "Premium full-flex business class. Fully changeable for free. Fully refundable for a 100% refund. Includes priority boarding and lounge access."},
        {"code": "C", "name": "Semi-restricted business", "change_fee_inr": 15000, "refund_pct": 80, "description": "Semi-flexible business class class. Changeable for INR 15,000 fee. 80% refund on cancellation."},
        {"code": "D", "name": "Discounted business", "change_fee_inr": 25000, "refund_pct": 0, "description": "Discounted business class fare. Changeable with a high fee of INR 25,000. Absolutely non-refundable."},
        {"code": "G", "name": "Group fare", "change_fee_inr": 10000, "refund_pct": 25, "description": "Special group booking conditions apply. Changeable for INR 10,000. 25% refund on cancellation. Requires a minimum of 10 passengers."}
    ],
    "waivers": [
        {
            "id": "WX-2026-INDIA",
            "type": "weather",
            "description": "Mumbai monsoon weather disruption",
            "valid_from": "2026-06-22",
            "valid_until": "2026-06-30",
            "origin_codes": ["BOM", "DEL"],
            "applies_to": ["all routes"],
            "fee_waived": True,
            "discount_pct": 0
        },
        {
            "id": "OPS-EK-2026-01",
            "type": "irops",
            "description": "Emirates schedule disruption Middle East",
            "valid_from": "2026-06-01",
            "valid_until": "2026-07-31",
            "origin_codes": ["BOM", "DEL", "BLR"],
            "applies_to": ["BOM-DXB", "DEL-DXB", "BLR-DXB"],
            "fee_waived": True,
            "discount_pct": 0
        },
        {
            "id": "CORP-AI-ANNUAL",
            "type": "corporate",
            "description": "Air India corporate agreement discount",
            "valid_from": "2026-01-01",
            "valid_until": "2026-12-31",
            "origin_codes": [],
            "applies_to": ["all AI routes"],
            "fee_waived": False,
            "discount_pct": 12
        },
        {
            "id": "EMRG-2026",
            "type": "emergency",
            "description": "Emergency travel exception, all routes all airlines",
            "valid_from": "2026-01-01",
            "valid_until": "2026-12-31",
            "origin_codes": [],
            "applies_to": ["all routes"],
            "fee_waived": True,
            "discount_pct": 0,
            "requires_code": True,
            "approval_required": True
        }
    ],
    "corporate_policies": [
        {
            "id": "CP-001",
            "name": "Standard Travel Policy",
            "allowed_cabins": ["ECONOMY"],
            "allowed_fare_classes": ["Y", "M", "K", "Q"],
            "max_fare_inr": 150000,
            "min_advance_days": 7,
            "preferred_airlines": ["AI", "6E"],
            "requires_approval_above_inr": 100000
        },
        {
            "id": "CP-002",
            "name": "Senior Management Travel Policy",
            "allowed_cabins": ["ECONOMY", "BUSINESS"],
            "allowed_fare_classes": ["Y", "M", "K", "J", "C", "D"],
            "max_fare_inr": 500000,
            "min_advance_days": 3,
            "preferred_airlines": ["AI", "EK", "QR"],
            "requires_approval_above_inr": 400000
        },
        {
            "id": "CP-003",
            "name": "Executive Grade Policy",
            "allowed_cabins": ["ECONOMY", "BUSINESS", "FIRST"],
            "allowed_fare_classes": ["Y", "M", "K", "Q", "J", "C", "D", "G"],
            "max_fare_inr": 9999999,
            "min_advance_days": 0,
            "preferred_airlines": ["AI", "EK", "QR", "SQ", "BA", "6E"],
            "requires_approval_above_inr": 9999999
        }
    ],
    "passengers": [
        {"id": "PASS-001", "name": "Aryan Mehta", "tier": "Gold", "policy_id": "CP-001"},
        {"id": "PASS-002", "name": "Priya Sharma", "tier": "Silver", "policy_id": "CP-001"},
        {"id": "PASS-003", "name": "Rajesh Kumar", "tier": "Platinum", "policy_id": "CP-002"},
        {"id": "PASS-004", "name": "Anita Singh", "tier": "Standard", "policy_id": "CP-001"},
        {"id": "PASS-005", "name": "Vikram Nair", "tier": "Executive", "policy_id": "CP-003"}
    ]
}
