import copy
import hashlib
import logging
import os
import re
import threading
import time
from datetime import date, datetime, timezone

from travel.mock_travel import get_mock_flights

logger = logging.getLogger(__name__)

_IATA_PATTERN = re.compile(r"^[A-Z]{3}$")
_CACHE_LOCK = threading.Lock()
_FLIGHT_CACHE: dict[tuple[str, str, str, str], tuple[float, list[dict]]] = {}


def _env_int(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, str(default))))
    except ValueError:
        return default


def _is_enabled(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _validate_search(origin: str, destination: str, travel_date: str) -> None:
    if not _IATA_PATTERN.fullmatch(origin) or not _IATA_PATTERN.fullmatch(destination):
        raise ValueError("Origin and destination must be three-letter IATA airport codes.")
    if origin == destination:
        raise ValueError("Origin and destination must be different airports.")

    parsed_date = date.fromisoformat(travel_date)
    if parsed_date < date.today():
        raise ValueError("Travel date must be today or in the future.")


def _format_datetime(value) -> str:
    year, month, day = value.date
    hour, minute = value.time
    return f"{year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}"


def _format_duration(minutes: int) -> str:
    hours, remaining_minutes = divmod(minutes, 60)
    if hours and remaining_minutes:
        return f"{hours}h {remaining_minutes}m"
    if hours:
        return f"{hours}h"
    return f"{remaining_minutes}m"


def _offer_id(search_key: tuple[str, str, str, str], index: int, departure: str, price: int) -> str:
    raw_value = "|".join((*search_key, str(index), departure, str(price)))
    return hashlib.sha256(raw_value.encode("utf-8")).hexdigest()[:16]


def _get_cached(search_key: tuple[str, str, str, str]) -> list[dict] | None:
    with _CACHE_LOCK:
        cached = _FLIGHT_CACHE.get(search_key)
        if not cached:
            return None
        expires_at, flights = cached
        if expires_at <= time.monotonic():
            _FLIGHT_CACHE.pop(search_key, None)
            return None

    cached_flights = copy.deepcopy(flights)
    for flight in cached_flights:
        flight["cache_status"] = "HIT"
    return cached_flights


def _set_cached(search_key: tuple[str, str, str, str], flights: list[dict]) -> None:
    ttl_seconds = _env_int("FLIGHT_SEARCH_CACHE_SECONDS", 600)
    with _CACHE_LOCK:
        _FLIGHT_CACHE[search_key] = (time.monotonic() + ttl_seconds, copy.deepcopy(flights))


def _search_google_flights(
    origin: str,
    destination: str,
    travel_date: str,
    cabin_class: str,
) -> list[dict]:
    from fast_flights import FlightQuery, Passengers, create_query, get_flights

    seat_lookup = {
        "ECONOMY": "economy",
        "PREMIUM_ECONOMY": "premium-economy",
        "BUSINESS": "business",
        "FIRST": "first",
    }
    fare_class_lookup = {
        "ECONOMY": "Y",
        "PREMIUM_ECONOMY": "W",
        "BUSINESS": "J",
        "FIRST": "F",
    }

    query = create_query(
        flights=[
            FlightQuery(
                date=travel_date,
                from_airport=origin,
                to_airport=destination,
            )
        ],
        seat=seat_lookup.get(cabin_class, "economy"),
        trip="one-way",
        passengers=Passengers(adults=1),
        language="en-GB",
        currency="INR",
    )
    results = get_flights(query)
    if not results:
        return []

    airline_name_to_code = {
        airline.name.casefold(): airline.code for airline in results.metadata.airlines
    }
    observed_at = datetime.now(timezone.utc).isoformat()
    search_url = query.url()
    search_key = (origin, destination, travel_date, cabin_class)
    result_limit = _env_int("FLIGHT_SEARCH_RESULT_LIMIT", 8)
    normalized_flights = []

    for index, result in enumerate(results[:result_limit]):
        if not result.flights:
            continue

        segments = []
        total_air_minutes = 0
        for segment in result.flights:
            total_air_minutes += segment.duration
            segments.append(
                {
                    "origin": segment.from_airport.code,
                    "origin_name": segment.from_airport.name,
                    "destination": segment.to_airport.code,
                    "destination_name": segment.to_airport.name,
                    "departure_time": _format_datetime(segment.departure),
                    "arrival_time": _format_datetime(segment.arrival),
                    "duration_minutes": segment.duration,
                    "plane_type": segment.plane_type,
                }
            )

        airline_names = result.airlines or ["Multiple airlines"]
        airline_codes = [
            airline_name_to_code.get(name.casefold())
            for name in airline_names
            if airline_name_to_code.get(name.casefold())
        ]
        if not airline_codes and result.type and result.type != "multi":
            airline_codes = [result.type]

        primary_airline_code = airline_codes[0] if airline_codes else "MULTI"
        departure_time = segments[0]["departure_time"]
        arrival_time = segments[-1]["arrival_time"]
        transit_airports = [segment["destination"] for segment in segments[:-1]]

        normalized_flights.append(
            {
                "offer_id": _offer_id(search_key, index, departure_time, result.price),
                "flight_number": " / ".join(airline_codes) or primary_airline_code,
                "airline": primary_airline_code,
                "airline_name": " + ".join(airline_names),
                "airline_codes": airline_codes,
                "origin": origin,
                "destination": destination,
                "departure_time": departure_time,
                "arrival_time": arrival_time,
                "duration": _format_duration(total_air_minutes),
                "duration_minutes": total_air_minutes,
                "stops": max(0, len(segments) - 1),
                "transit_airport": ", ".join(transit_airports) if transit_airports else None,
                "segments": segments,
                "cabin_class": cabin_class,
                "fare_class": fare_class_lookup.get(cabin_class, "Y"),
                "fare_class_estimated": True,
                "price_inr": int(result.price),
                "currency": "INR",
                "availability": "Verify on Google Flights",
                "source": "GOOGLE_FLIGHTS",
                "price_source": "Google Flights",
                "is_live_price": True,
                "observed_at": observed_at,
                "cache_status": "MISS",
                "search_url": search_url,
                "price_note": "Live comparison fare observed on Google Flights; verify before booking.",
                "carbon_emissions_kg": round(result.carbon.emission / 1000, 1),
                "typical_carbon_emissions_kg": round(result.carbon.typical_on_route / 1000, 1),
            }
        )

    return normalized_flights


def _mock_flights(
    origin: str,
    destination: str,
    travel_date: str,
    cabin_class: str,
    fallback_reason: str | None = None,
) -> list[dict]:
    observed_at = datetime.now(timezone.utc).isoformat()
    search_key = (origin, destination, travel_date, cabin_class)
    flights = get_mock_flights(origin, destination, travel_date, cabin_class)

    for index, flight in enumerate(flights):
        flight["offer_id"] = _offer_id(
            search_key,
            index,
            flight["departure_time"],
            flight["price_inr"],
        )
        flight["airline_name"] = flight["airline"]
        flight["currency"] = "INR"
        flight["source"] = "MOCK_FALLBACK"
        flight["price_source"] = "Estimated demo fallback"
        flight["is_live_price"] = False
        flight["observed_at"] = observed_at
        flight["cache_status"] = "MISS"
        flight["search_url"] = None
        flight["price_note"] = "Estimated fallback fare; not a live market price."
        flight["fallback_reason"] = fallback_reason
        flight["fare_class_estimated"] = True

    return flights


def search_flights_api(
    origin: str,
    dest: str,
    date: str,
    cabin_class: str = "ECONOMY",
) -> list[dict]:
    origin = origin.upper().strip()
    destination = dest.upper().strip()
    cabin_class = cabin_class.upper().strip().replace(" ", "_").replace("-", "_")
    _validate_search(origin, destination, date)

    search_key = (origin, destination, date, cabin_class)
    cached = _get_cached(search_key)
    if cached is not None:
        logger.info("Returning cached flight comparison for %s-%s on %s", origin, destination, date)
        return cached

    mode = os.getenv("FLIGHT_DATA_MODE", "google_flights").strip().lower()
    if mode == "mock":
        flights = _mock_flights(origin, destination, date, cabin_class)
    else:
        try:
            logger.info("Fetching Google Flights comparison for %s-%s on %s", origin, destination, date)
            flights = _search_google_flights(origin, destination, date, cabin_class)
            if not flights:
                raise LookupError("Google Flights returned no matching itineraries.")
        except Exception as error:
            if not _is_enabled("ALLOW_MOCK_FLIGHT_FALLBACK", True):
                raise
            logger.warning("Google Flights lookup failed; using marked demo fallback: %s", error)
            flights = _mock_flights(
                origin,
                destination,
                date,
                cabin_class,
                fallback_reason=str(error),
            )

    _set_cached(search_key, flights)
    return copy.deepcopy(flights)


def search_flights_formatted(
    origin: str,
    dest: str,
    date: str,
    cabin_class: str = "ECONOMY",
) -> str:
    flights = search_flights_api(origin, dest, date, cabin_class)
    if not flights:
        return "No flights found for this route and date."

    source = flights[0].get("price_source", "Unknown source")
    lines = [f"Available flight options for {origin} -> {dest} on {date} ({cabin_class}) from {source}:"]
    for index, flight in enumerate(flights, 1):
        stops = "Direct" if flight["stops"] == 0 else f"{flight['stops']}-stop"
        lines.append(
            f"{index}. {flight.get('airline_name', flight['airline'])} ({flight['flight_number']}) | "
            f"Dep: {flight['departure_time']} - Arr: {flight['arrival_time']} | "
            f"{stops} | Price: INR {flight['price_inr']:,} | "
            f"Cabin: {flight.get('cabin_class', cabin_class)}"
        )

    lines.append(f"Source note: {flights[0].get('price_note', '')}")
    if flights[0].get("search_url"):
        lines.append(f"Verify: {flights[0]['search_url']}")
    return "\n".join(lines)
