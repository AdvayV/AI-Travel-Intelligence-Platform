import logging

logger = logging.getLogger(__name__)

CITY_ALIASES = {
    "DXB": ["Dubai"],
    "LHR": ["London"],
    "SIN": ["Singapore"],
    "BKK": ["Bangkok", "Thailand"],
    "JFK": ["New York", "NYC"],
    "DOH": ["Doha", "Qatar"],
    "KUL": ["Kuala Lumpur", "Malaysia"],
    "NRT": ["Tokyo", "Japan"],
    "CDG": ["Paris", "France"],
    "SYD": ["Sydney", "Australia"],
    "FRA": ["Frankfurt", "Germany"],
    "AMS": ["Amsterdam", "Netherlands"],
    "BOM": ["Mumbai"],
    "DEL": ["Delhi"],
    "BLR": ["Bengaluru", "Bangalore"],
    "MAA": ["Chennai"],
    "HYD": ["Hyderabad"],
    "HKG": ["Hong Kong"],
    "ICN": ["Seoul", "Korea"],
    "ORD": ["Chicago"],
    "YYZ": ["Toronto", "Canada"],
    "MEL": ["Melbourne"],
    "SFO": ["San Francisco"],
    "CGK": ["Jakarta", "Bali", "Indonesia"],
    "MNL": ["Manila", "Philippines"],
    "SGN": ["Ho Chi Minh", "Saigon", "Vietnam"],
    "CMB": ["Colombo", "Sri Lanka"],
    "JED": ["Jeddah", "Saudi Arabia"]
}

def get_trend_scores(dest_codes: list[str]) -> dict:
    """
    Fetch Google Trends interest using pytrends library.
    Falls back to 0.0 scores if pytrends is unavailable or rate-limited.
    """
    scores = {code: 0.0 for code in dest_codes}

    try:
        from pytrends.request import TrendReq

        # Use a single keyword per batch to avoid rate limits
        pytrends = TrendReq(hl='en-IN', tz=330, timeout=(5, 10), retries=1, backoff_factor=0.5)

        for code in dest_codes:
            aliases = CITY_ALIASES.get(code, [code])
            keyword = aliases[0]  # Use the primary city name
            try:
                pytrends.build_payload([keyword], cat=0, timeframe='now 7-d', geo='IN')
                interest_df = pytrends.interest_over_time()
                if not interest_df.empty and keyword in interest_df.columns:
                    avg_interest = float(interest_df[keyword].mean())
                    # Normalise 0-100 Google Trends score to 0-0.3 signal bonus
                    scores[code] = round(min(0.3, avg_interest / 100.0 * 0.3), 3)
            except Exception as inner_e:
                logger.debug(f"pytrends failed for {code}/{keyword}: {inner_e}")
                scores[code] = 0.0

    except ImportError:
        logger.warning("pytrends not installed. Run: pip install pytrends. Using zero trend scores.")
    except Exception as e:
        logger.warning(f"Trends fetch failed entirely: {e}. Using zero trend scores.")

    return scores
