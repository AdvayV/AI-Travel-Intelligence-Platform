import os
import time
import httpx
import logging
from dotenv import load_dotenv

load_dotenv()

TRAVEL_CLIENT_ID = os.getenv("TRAVEL_CLIENT_ID")
TRAVEL_CLIENT_SECRET = os.getenv("TRAVEL_CLIENT_SECRET")
TRAVEL_AUTH_URL = "https://api.cert.travel.com/v2/auth/token"

logger = logging.getLogger(__name__)

_token_cache = {
    "token": None,
    "expires_at": 0
}

def has_travel_credentials() -> bool:
    return bool(TRAVEL_CLIENT_ID and TRAVEL_CLIENT_SECRET and TRAVEL_CLIENT_ID != "your_travel_client_id_here")

def get_travel_token() -> str:
    if not has_travel_credentials():
        raise ValueError("Travel credentials not set or placeholder used")
    
    if _token_cache["token"] and time.time() < _token_cache["expires_at"]:
        return _token_cache["token"]

    auth_data = {
        "grant_type": "client_credentials"
    }
    logger.info("Requesting new Travel access token")
    # Travel authentication uses Client Credentials Flow with Client ID and Secret passed via Basic Auth or POST body.
    # The v1 uses basic auth: auth=(TRAVEL_CLIENT_ID, TRAVEL_CLIENT_SECRET)
    response = httpx.post(TRAVEL_AUTH_URL, data=auth_data, auth=(TRAVEL_CLIENT_ID, TRAVEL_CLIENT_SECRET))
    response.raise_for_status()
    data = response.json()
    _token_cache["token"] = data["access_token"]
    # Token expires in 604800 seconds by default
    _token_cache["expires_at"] = time.time() + data.get("expires_in", 604800) - 60
    return _token_cache["token"]
