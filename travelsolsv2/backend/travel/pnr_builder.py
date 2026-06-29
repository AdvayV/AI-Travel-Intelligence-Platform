import logging
from travel.mock_travel import generate_pnr

logger = logging.getLogger(__name__)


def create_pnr_api(passenger_name: str, flight_number: str, origin: str, dest: str, date: str, fare_class: str, price: int) -> dict:
    logger.info(f"Generating mock PNR booking for passenger {passenger_name}")
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

