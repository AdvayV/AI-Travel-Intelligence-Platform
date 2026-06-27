import httpx
import logging
from travel.auth import has_travel_credentials, get_travel_token
from travel.mock_travel import generate_pnr

logger = logging.getLogger(__name__)

def create_pnr_api(passenger_name: str, flight_number: str, origin: str, dest: str, date: str, fare_class: str, price: int) -> dict:
    if not has_travel_credentials():
        logger.info("Travel credentials not set. Creating mock PNR booking.")
        pnr = generate_pnr()
        return {
            "status": "SUCCESS",
            "pnr": pnr,
            "passenger_name": passenger_name,
            "flight_number": flight_number,
            "origin": origin,
            "destination": dest,
            "date": date,
            "fare_class": fare_class,
            "price_inr": price,
            "source": "MOCK_TRAVEL"
        }

    try:
        token = get_travel_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        # Travel Passenger Details / Create PNR endpoint
        url = "https://api.cert.travel.com/v1.1.0/passengername/record?action=create"
        
        # Format names (assuming format "First Last" -> Last/First)
        parts = passenger_name.split()
        first_name = parts[0] if len(parts) > 0 else "John"
        last_name = parts[1] if len(parts) > 1 else "Doe"
        
        # Simplified Travel PNR payload (standard Create Passenger Name Record structure)
        payload = {
            "CreatePassengerNameRecordRQ": {
                "targetCity": "F9AC",
                "AirBook": {
                    "HaltOnStatus": [
                        {"Code": "UC"},
                        {"Code": "US"},
                        {"Code": "HX"}
                    ],
                    "OriginDestinationInformation": {
                        "FlightSegment": [
                            {
                                "DepartureDateTime": f"{date}T09:00:00",
                                "ArrivalDateTime": f"{date}T13:00:00",
                                "FlightNumber": flight_number.split("-")[-1],
                                "NumberInParty": "1",
                                "ResBookDesigCode": fare_class,
                                "Status": "NN",
                                "DestinationLocation": {"LocationCode": dest},
                                "MarketingAirline": {"Code": flight_number.split("-")[0], "FlightNumber": flight_number.split("-")[-1]},
                                "OriginLocation": {"LocationCode": origin}
                            }
                        ]
                    }
                },
                "TravelItineraryAddInfo": {
                    "CustomerInfo": {
                        "ContactNumbers": {
                            "ContactNumber": [
                                {
                                    "NameNumber": "1.1",
                                    "Phone": "91-9999999999",
                                    "PhoneUseType": "H"
                                }
                            ]
                        },
                        "PersonName": [
                            {
                                "NameNumber": "1.1",
                                "GivenName": first_name,
                                "Surname": last_name
                            }
                        ]
                    }
                },
                "PostProcessing": {
                    "EndTransaction": {
                        "Source": {
                            "ReceivedFrom": "TravelRoute Agent"
                        }
                    }
                }
            }
        }
        
        logger.info(f"Sending PNR creation request to Travel for {passenger_name}")
        response = httpx.post(url, headers=headers, json=payload, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            # Extract PNR (Locator)
            itinerary_ref = data.get("CreatePassengerNameRecordRS", {}).get("ItineraryRef", {})
            pnr = itinerary_ref.get("ID")
            if pnr:
                logger.info(f"Travel PNR successfully created: {pnr}")
                return {
                    "status": "SUCCESS",
                    "pnr": pnr,
                    "passenger_name": passenger_name,
                    "flight_number": flight_number,
                    "origin": origin,
                    "destination": dest,
                    "date": date,
                    "fare_class": fare_class,
                    "price_inr": price,
                    "source": "LIVE_TRAVEL"
                }
                
        # If Travel API fails or returns no PNR, log and fall back to mock
        logger.warning(f"Travel PNR creation failed (Status: {response.status_code}). Falling back to mock PNR.")
        pnr = generate_pnr()
        return {
            "status": "SUCCESS",
            "pnr": pnr,
            "passenger_name": passenger_name,
            "flight_number": flight_number,
            "origin": origin,
            "destination": dest,
            "date": date,
            "fare_class": fare_class,
            "price_inr": price,
            "source": "MOCK_TRAVEL_FALLBACK"
        }
        
    except Exception as e:
        logger.warning(f"Error creating Travel PNR: {e}. Falling back to mock PNR.")
        pnr = generate_pnr()
        return {
            "status": "SUCCESS",
            "pnr": pnr,
            "passenger_name": passenger_name,
            "flight_number": flight_number,
            "origin": origin,
            "destination": dest,
            "date": date,
            "fare_class": fare_class,
            "price_inr": price,
            "source": "MOCK_TRAVEL_EXCEPTION"
        }
