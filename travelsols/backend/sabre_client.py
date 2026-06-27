import os
import time
import logging
import httpx
from dotenv import load_dotenv
from mock_sabre_data import get_mock_snapshots

load_dotenv()

SABRE_CLIENT_ID = os.getenv("SABRE_CLIENT_ID")
SABRE_CLIENT_SECRET = os.getenv("SABRE_CLIENT_SECRET")
SABRE_AUTH_URL = "https://api.cert.sabre.com/v2/auth/token"
SABRE_API_URL = "https://api.cert.sabre.com/v1/lists/top/destinations"

_token_cache = {
    "token": None,
    "expires_at": 0
}

logger = logging.getLogger(__name__)

def _get_token() -> str:
    if not SABRE_CLIENT_ID or not SABRE_CLIENT_SECRET:
        raise ValueError("Sabre credentials not set")
    
    if _token_cache["token"] and time.time() < _token_cache["expires_at"]:
        return _token_cache["token"]

    auth_data = {
        "grant_type": "client_credentials"
    }
    response = httpx.post(SABRE_AUTH_URL, data=auth_data, auth=(SABRE_CLIENT_ID, SABRE_CLIENT_SECRET))
    response.raise_for_status()
    data = response.json()
    _token_cache["token"] = data["access_token"]
    # Token expires in 604800 seconds
    _token_cache["expires_at"] = time.time() + data.get("expires_in", 604800) - 60
    return _token_cache["token"]

def get_top_destinations(origin: str) -> dict:
    if not SABRE_CLIENT_ID or not SABRE_CLIENT_SECRET:
        logger.warning("Sabre credentials missing. Using mock data.")
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
            response = httpx.get(SABRE_API_URL, headers=headers, params=params, timeout=10)
            if response.status_code != 200:
                logger.warning(f"Sabre API returned {response.status_code}. Falling back to mock data.")
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
        logger.warning(f"Failed to fetch Sabre data: {e}. Using mock data.")
        return get_mock_snapshots(origin)
