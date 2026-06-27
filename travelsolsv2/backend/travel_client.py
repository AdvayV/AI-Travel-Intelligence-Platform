import os
import time
import logging
import base64
import httpx
from dotenv import load_dotenv
from mock_travel_data import get_mock_snapshots

load_dotenv()

TRAVEL_CLIENT_ID = os.getenv("TRAVEL_CLIENT_ID")
TRAVEL_CLIENT_SECRET = os.getenv("TRAVEL_CLIENT_SECRET")
TRAVEL_AUTH_URL = "https://api.cert.travel.com/v2/auth/token"
TRAVEL_API_URL = "https://api.cert.travel.com/v1/lists/top/destinations"

_token_cache = {
    "token": None,
    "expires_at": 0
}

logger = logging.getLogger(__name__)

def _get_token() -> str:
    if not TRAVEL_CLIENT_ID or not TRAVEL_CLIENT_SECRET:
        raise ValueError("Travel credentials not set")
    
    if _token_cache["token"] and time.time() < _token_cache["expires_at"]:
        return _token_cache["token"]

    # Step 1: Base64 encode client_id
    cid_b64 = base64.b64encode(TRAVEL_CLIENT_ID.encode()).decode()
    # Step 2: Base64 encode client_secret
    sec_b64 = base64.b64encode(TRAVEL_CLIENT_SECRET.encode()).decode()
    # Step 3: Combine with colon and encode again
    combined = f"{cid_b64}:{sec_b64}"
    final_b64 = base64.b64encode(combined.encode()).decode()

    headers = {
        "Authorization": f"Basic {final_b64}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    auth_data = {
        "grant_type": "client_credentials"
    }
    
    response = httpx.post(TRAVEL_AUTH_URL, data=auth_data, headers=headers)
    response.raise_for_status()
    data = response.json()
    _token_cache["token"] = data["access_token"]
    # Token expires in 604800 seconds
    _token_cache["expires_at"] = time.time() + data.get("expires_in", 604800) - 60
    return _token_cache["token"]

def get_top_destinations(origin: str) -> dict:
    if not TRAVEL_CLIENT_ID or not TRAVEL_CLIENT_SECRET:
        logger.warning("Travel credentials missing. Using mock data.")
        return get_mock_snapshots(origin)
    
    try:
        token = _get_token()
        headers = {"Authorization": f"Bearer {token}"}
        snapshots = {"2w": {}, "8w": {}, "12w": {}}
        
        for duration in [2, 8, 12]:
            params = {
                "origin": origin,
                "lookuptype": "HISTORICAL",
                "topdestinationcount": 50,
                "pointofsalecountry": "IN",
                "historicalduration": duration
            }
            response = httpx.get(TRAVEL_API_URL, headers=headers, params=params, timeout=10)
            if response.status_code != 200:
                logger.warning(f"Travel API returned {response.status_code}. Falling back to mock data.")
                return get_mock_snapshots(origin)
            
            data = response.json()
            destinations = data.get("Destinations", [])
            key = f"{duration}w"
            for dest in destinations:
                dest_code = dest.get("DestinationLocation")
                rank = dest.get("Rank", 50)
                demand_score = (51 - rank) / 50.0
                snapshots[key][dest_code] = demand_score
                
        return {"origin": origin, "snapshots": snapshots}
    except Exception as e:
        logger.warning(f"Failed to fetch Travel data: {e}. Using mock data.")
        return get_mock_snapshots(origin)
