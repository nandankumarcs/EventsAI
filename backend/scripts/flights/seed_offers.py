#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import os
import sys
import time
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from decimal import Decimal
from io import StringIO
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import requests
from requests import HTTPError
from requests.exceptions import RequestException

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402
from django.conf import settings  # noqa: E402
from django.db import transaction  # noqa: E402

django.setup()

from apps.flights.models import FlightOffer  # noqa: E402

IST = ZoneInfo("Asia/Kolkata")
AVIATIONSTACK_PROVIDER = "aviationstack"

INDIA_AIRPORTS: dict[str, dict[str, str]] = {
    "DEL": {"city": "New Delhi", "state": "Delhi", "airport_name": "Indira Gandhi International Airport"},
    "BOM": {"city": "Mumbai", "state": "Maharashtra", "airport_name": "Chhatrapati Shivaji Maharaj International Airport"},
    "BLR": {"city": "Bengaluru", "state": "Karnataka", "airport_name": "Kempegowda International Airport"},
    "HYD": {"city": "Hyderabad", "state": "Telangana", "airport_name": "Rajiv Gandhi International Airport"},
    "MAA": {"city": "Chennai", "state": "Tamil Nadu", "airport_name": "Chennai International Airport"},
    "CCU": {"city": "Kolkata", "state": "West Bengal", "airport_name": "Netaji Subhas Chandra Bose International Airport"},
    "PNQ": {"city": "Pune", "state": "Maharashtra", "airport_name": "Pune Airport"},
    "AMD": {"city": "Ahmedabad", "state": "Gujarat", "airport_name": "Sardar Vallabhbhai Patel International Airport"},
    "GOI": {"city": "Goa", "state": "Goa", "airport_name": "Goa International Airport"},
    "COK": {"city": "Kochi", "state": "Kerala", "airport_name": "Cochin International Airport"},
}


@dataclass(slots=True)
class NormalizedFlightOffer:
    listing_code: str
    provider: str
    provider_offer_id: str
    source_label: str
    origin_iata: str
    origin_airport_name: str
    origin_city: str
    origin_state: str
    destination_iata: str
    destination_airport_name: str
    destination_city: str
    destination_state: str
    departure_date: date
    departure_at: datetime
    arrival_at: datetime
    airline_code: str
    airline_name: str
    flight_number: str
    cabin_class: str
    stops: int
    refundable: bool
    baggage_summary: str
    fare_brand: str
    currency: str
    total_amount: Decimal | None
    offer_expires_at: datetime | None
    metadata: dict[str, Any]


@dataclass(slots=True)
class AirportEnrichment:
    name: str
    city: str
    country: str
    iata: str


@dataclass(slots=True)
class AirlineEnrichment:
    name: str
    iata: str
    icao: str


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Seed India-only flight offers into flight_offers.")
    parser.add_argument("--start-date", help="Seed start date in YYYY-MM-DD. Defaults to today + 8 days.")
    parser.add_argument("--days", type=int, default=1, help="Number of departure dates to seed from the start date.")
    parser.add_argument(
        "--origins",
        default=",".join(INDIA_AIRPORTS.keys()),
        help="Comma-separated origin airport IATA codes to fetch from Aviationstack.",
    )
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=0.0,
        help="Optional delay between Aviationstack requests to respect plan limits.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Normalize rows without writing them to the database.")
    parser.add_argument(
        "--skip-openflights-enrichment",
        action="store_true",
        help="Skip OpenFlights enrichment for airport and airline labels.",
    )
    parser.add_argument(
        "--mark-stale-unpublished",
        action="store_true",
        help="Mark existing Aviationstack rows unpublished when they are not present in the current run.",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=2,
        help="Maximum retries per Aviationstack request when rate-limited or transient failures occur.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    access_key = getattr(settings, "AVIATIONSTACK_ACCESS_KEY", "")
    if not access_key:
        parser.error("AVIATIONSTACK_ACCESS_KEY is not configured in backend/.env or environment.")

    start_date = parse_start_date(args.start_date)
    origin_codes = [code.strip().upper() for code in args.origins.split(",") if code.strip()]
    unsupported_codes = [code for code in origin_codes if code not in INDIA_AIRPORTS]
    if unsupported_codes:
        parser.error(f"Unsupported origin codes: {', '.join(sorted(unsupported_codes))}")

    print(
        f"[seed] starting Aviationstack seed: start_date={start_date.isoformat()} days={args.days} "
        f"origins={','.join(origin_codes)} dry_run={args.dry_run}",
        flush=True,
    )

    session = requests.Session()
    aviationstack_rows = fetch_aviationstack_rows(
        session=session,
        access_key=access_key,
        start_date=start_date,
        days=args.days,
        origin_codes=origin_codes,
        sleep_seconds=args.sleep_seconds,
        max_retries=args.max_retries,
    )

    print(f"[seed] fetched and normalized {len(aviationstack_rows)} Aviationstack rows before enrichment", flush=True)

    if args.skip_openflights_enrichment:
        normalized_rows = aviationstack_rows
        print("[seed] skipping OpenFlights enrichment", flush=True)
    else:
        print("[seed] starting OpenFlights enrichment", flush=True)
        normalized_rows = enrich_with_openflights(session=session, rows=aviationstack_rows)
        print(f"[seed] OpenFlights enrichment complete for {len(normalized_rows)} rows", flush=True)

    if args.dry_run:
        print(f"Prepared {len(normalized_rows)} normalized domestic India rows.")
        for row in normalized_rows[:10]:
            print(f"- {row.listing_code}: {row.origin_city} -> {row.destination_city} ({row.flight_number})")
        return 0

    created, updated, unpublished = persist_rows(
        normalized_rows,
        mark_stale_unpublished=args.mark_stale_unpublished,
    )
    print(
        f"Seed complete. Created {created}, updated {updated}, unpublished {unpublished}, "
        f"total processed {len(normalized_rows)}."
    )
    return 0


def parse_start_date(raw_value: str | None) -> date:
    if raw_value:
        return date.fromisoformat(raw_value)
    return date.today() + timedelta(days=8)


def fetch_aviationstack_rows(
    *,
    session: requests.Session,
    access_key: str,
    start_date: date,
    days: int,
    origin_codes: list[str],
    sleep_seconds: float,
    max_retries: int,
) -> list[NormalizedFlightOffer]:
    rows: list[NormalizedFlightOffer] = []
    batched_origins = ",".join(origin_codes)
    for day_offset in range(days):
        target_date = start_date + timedelta(days=day_offset)
        print(f"[seed] processing departure date {target_date.isoformat()}", flush=True)
        normalized_batch = fetch_for_date(
            session=session,
            access_key=access_key,
            target_date=target_date,
            origin_codes=origin_codes,
            batched_origins=batched_origins,
            max_retries=max_retries,
            sleep_seconds=sleep_seconds,
        )
        rows.extend(normalized_batch)
        if sleep_seconds > 0 and day_offset < days - 1:
            print(f"[seed] sleeping {sleep_seconds:.0f}s before next request", flush=True)
            time.sleep(sleep_seconds)
    return dedupe_rows(rows)


def fetch_for_date(
    *,
    session: requests.Session,
    access_key: str,
    target_date: date,
    origin_codes: list[str],
    batched_origins: str,
    max_retries: int,
    sleep_seconds: float,
) -> list[NormalizedFlightOffer]:
    if len(origin_codes) == 1:
        payload = fetch_aviationstack_schedule(
            session=session,
            access_key=access_key,
            airport_iatas=batched_origins,
            target_date=target_date,
            max_retries=max_retries,
        )
        normalized_batch = normalize_aviationstack_schedule(payload, target_date=target_date)
        print(
            f"[seed] normalized {len(normalized_batch)} domestic rows for origins={batched_origins} "
            f"date={target_date.isoformat()}",
            flush=True,
        )
        return normalized_batch

    print(
        f"[seed] requesting Aviationstack for origins={batched_origins} date={target_date.isoformat()}",
        flush=True,
    )
    try:
        payload = fetch_aviationstack_schedule(
            session=session,
            access_key=access_key,
            airport_iatas=batched_origins,
            target_date=target_date,
            max_retries=max_retries,
        )
    except HTTPError as exc:
        status_code = exc.response.status_code if exc.response is not None else None
        if status_code != 400:
            raise
        print(
            f"[seed] Aviationstack rejected batched origins for {target_date.isoformat()}; "
            "falling back to single-origin requests.",
            flush=True,
        )
        fallback_rows: list[NormalizedFlightOffer] = []
        for index, origin_code in enumerate(origin_codes):
            print(f"[seed] requesting Aviationstack for origin={origin_code} date={target_date.isoformat()}", flush=True)
            payload = fetch_aviationstack_schedule(
                session=session,
                access_key=access_key,
                airport_iatas=origin_code,
                target_date=target_date,
                max_retries=max_retries,
            )
            origin_rows = normalize_aviationstack_schedule(payload, target_date=target_date)
            fallback_rows.extend(origin_rows)
            print(
                f"[seed] normalized {len(origin_rows)} domestic rows for origin={origin_code} "
                f"date={target_date.isoformat()}",
                flush=True,
            )
            if sleep_seconds > 0 and index < len(origin_codes) - 1:
                print(f"[seed] sleeping {sleep_seconds:.0f}s before next request", flush=True)
                time.sleep(sleep_seconds)
        return fallback_rows

    normalized_batch = normalize_aviationstack_schedule(payload, target_date=target_date)
    print(
        f"[seed] normalized {len(normalized_batch)} domestic rows for origins={batched_origins} "
        f"date={target_date.isoformat()}",
        flush=True,
    )
    return normalized_batch


def fetch_aviationstack_schedule(
    *,
    session: requests.Session,
    access_key: str,
    airport_iatas: str,
    target_date: date,
    max_retries: int,
) -> dict[str, Any]:
    base_url = getattr(settings, "AVIATIONSTACK_BASE_URL", "https://api.aviationstack.com/v1").rstrip("/")
    timeout = float(getattr(settings, "AVIATIONSTACK_TIMEOUT_SECONDS", 20.0))
    params = {
        "access_key": access_key,
        "iataCode": airport_iatas,
        "type": "departure",
        "date": target_date.isoformat(),
    }
    attempt = 0
    while True:
        response = session.get(
            f"{base_url}/flightsFuture",
            params=params,
            timeout=timeout,
        )
        if response.status_code == 429 and attempt < max_retries:
            retry_after_header = response.headers.get("Retry-After")
            try:
                retry_after = float(retry_after_header) if retry_after_header else 65.0
            except ValueError:
                retry_after = 65.0
            print(
                f"Aviationstack rate limit hit for {airport_iatas} on {target_date.isoformat()}, "
                f"retrying in {retry_after:.0f}s...",
                file=sys.stderr,
                flush=True,
            )
            time.sleep(retry_after)
            attempt += 1
            continue

        response.raise_for_status()
        payload = response.json()
        if payload.get("error"):
            message = payload["error"].get("message", "Unknown Aviationstack error")
            raise RuntimeError(f"Aviationstack API error for {airport_iatas} on {target_date.isoformat()}: {message}")
        return payload


def normalize_aviationstack_schedule(
    payload: dict[str, Any],
    *,
    target_date: date,
) -> list[NormalizedFlightOffer]:
    data = payload.get("data", [])
    if not isinstance(data, list):
        print(
            f"[seed] skipping unexpected Aviationstack payload for {target_date.isoformat()}: "
            f"data is {type(data).__name__}, not list",
            flush=True,
        )
        return []

    rows: list[NormalizedFlightOffer] = []
    for item in data:
        if not isinstance(item, dict):
            print(
                f"[seed] skipping unexpected Aviationstack item for {target_date.isoformat()}: "
                f"{type(item).__name__}",
                flush=True,
            )
            continue
        normalized = normalize_aviationstack_item(item, target_date=target_date)
        if normalized is not None:
            rows.append(normalized)
    return rows


def normalize_aviationstack_item(
    item: dict[str, Any],
    *,
    target_date: date,
) -> NormalizedFlightOffer | None:
    departure = item.get("departure") or {}
    arrival = item.get("arrival") or {}
    airline = item.get("codeshared", {}).get("airline") or item.get("airline") or {}
    flight = item.get("codeshared", {}).get("flight") or item.get("flight") or {}

    origin_iata = str(departure.get("iataCode") or "").upper()
    destination_iata = str(arrival.get("iataCode") or "").upper()
    if origin_iata not in INDIA_AIRPORTS or destination_iata not in INDIA_AIRPORTS:
        return None
    if origin_iata == destination_iata:
        return None

    origin_info = INDIA_AIRPORTS[origin_iata]
    destination_info = INDIA_AIRPORTS[destination_iata]
    departure_at = parse_schedule_datetime(target_date, departure.get("scheduledTime"))
    arrival_at = parse_schedule_datetime(target_date, arrival.get("scheduledTime"), departure_at=departure_at)
    if not departure_at or not arrival_at:
        return None

    airline_code = str(airline.get("iataCode") or "").upper()
    flight_number = str(flight.get("number") or "").strip()
    iata_number = str(flight.get("iataNumber") or "").upper().replace(" ", "")
    provider_offer_id = build_provider_offer_id(
        origin_iata=origin_iata,
        destination_iata=destination_iata,
        departure_at=departure_at,
        flight_number=flight_number or iata_number,
        airline_code=airline_code,
    )

    airline_name = str(airline.get("name") or "").strip()
    listing_code = build_listing_code(provider_offer_id)

    return NormalizedFlightOffer(
        listing_code=listing_code,
        provider=AVIATIONSTACK_PROVIDER,
        provider_offer_id=provider_offer_id,
        source_label="aviationstack",
        origin_iata=origin_iata,
        origin_airport_name=origin_info["airport_name"],
        origin_city=origin_info["city"],
        origin_state=origin_info["state"],
        destination_iata=destination_iata,
        destination_airport_name=destination_info["airport_name"],
        destination_city=destination_info["city"],
        destination_state=destination_info["state"],
        departure_date=departure_at.date(),
        departure_at=departure_at,
        arrival_at=arrival_at,
        airline_code=airline_code,
        airline_name=airline_name,
        flight_number=flight_number or iata_number,
        cabin_class="",
        stops=0,
        refundable=False,
        baggage_summary="",
        fare_brand="",
        currency="",
        total_amount=None,
        offer_expires_at=None,
        metadata={"aviationstack": item},
    )


def parse_schedule_datetime(
    flight_date: date,
    raw_time: Any,
    *,
    departure_at: datetime | None = None,
) -> datetime | None:
    if raw_time in {None, ""}:
        return None
    text = str(raw_time).strip()
    try:
        if "T" in text:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=IST)
            return parsed.astimezone(IST)
        parsed_time = datetime.strptime(text, "%H:%M").time()
    except ValueError:
        try:
            parsed_time = datetime.strptime(text, "%H:%M:%S").time()
        except ValueError:
            return None

    combined = datetime.combine(flight_date, parsed_time, tzinfo=IST)
    if departure_at and combined < departure_at:
        return combined + timedelta(days=1)
    return combined


def build_provider_offer_id(
    *,
    origin_iata: str,
    destination_iata: str,
    departure_at: datetime,
    flight_number: str,
    airline_code: str,
) -> str:
    return "|".join(
        [
            airline_code or "NA",
            flight_number or "NA",
            origin_iata,
            destination_iata,
            departure_at.isoformat(),
        ]
    )


def build_listing_code(provider_offer_id: str) -> str:
    digest = hashlib.sha1(provider_offer_id.encode("utf-8")).hexdigest()[:12].upper()
    return f"FLT-{digest}"


def dedupe_rows(rows: list[NormalizedFlightOffer]) -> list[NormalizedFlightOffer]:
    deduped: dict[str, NormalizedFlightOffer] = {}
    for row in rows:
        deduped[row.provider_offer_id] = row
    return list(deduped.values())


def enrich_with_openflights(
    *,
    session: requests.Session,
    rows: list[NormalizedFlightOffer],
) -> list[NormalizedFlightOffer]:
    print("[seed] downloading OpenFlights airport and airline reference data", flush=True)
    airport_map, airline_map = load_openflights_reference_data(session=session)
    print(
        f"[seed] loaded OpenFlights reference data: airports={len(airport_map)} airlines={len(airline_map)}",
        flush=True,
    )
    enriched_rows: list[NormalizedFlightOffer] = []
    for row in rows:
        origin = airport_map.get(row.origin_iata)
        destination = airport_map.get(row.destination_iata)
        airline = airline_map.get(row.airline_code)
        enriched_rows.append(
            replace(
                row,
                origin_airport_name=row.origin_airport_name or (origin.name if origin else ""),
                destination_airport_name=row.destination_airport_name or (destination.name if destination else ""),
                airline_name=row.airline_name or (airline.name if airline else ""),
            )
        )
    return enriched_rows


def load_openflights_reference_data(
    *,
    session: requests.Session,
) -> tuple[dict[str, AirportEnrichment], dict[str, AirlineEnrichment]]:
    timeout = float(getattr(settings, "AVIATIONSTACK_TIMEOUT_SECONDS", 20.0))
    try:
        airports_response = session.get(getattr(settings, "OPENFLIGHTS_AIRPORTS_URL"), timeout=timeout)
        airports_response.raise_for_status()
        airlines_response = session.get(getattr(settings, "OPENFLIGHTS_AIRLINES_URL"), timeout=timeout)
        airlines_response.raise_for_status()
        return (
            parse_openflights_airports(airports_response.text),
            parse_openflights_airlines(airlines_response.text),
        )
    except RequestException as exc:
        print(
            f"[seed] OpenFlights enrichment unavailable ({exc.__class__.__name__}: {exc}); continuing without enrichment.",
            flush=True,
        )
        return {}, {}


def parse_openflights_airports(raw_text: str) -> dict[str, AirportEnrichment]:
    reader = csv.reader(StringIO(raw_text))
    result: dict[str, AirportEnrichment] = {}
    for row in reader:
        if len(row) < 9:
            continue
        iata = row[4].strip().upper()
        country = row[3].strip()
        if not iata or iata == "\\N" or country != "India":
            continue
        result[iata] = AirportEnrichment(
            name=row[1].strip(),
            city=row[2].strip(),
            country=country,
            iata=iata,
        )
    return result


def parse_openflights_airlines(raw_text: str) -> dict[str, AirlineEnrichment]:
    reader = csv.reader(StringIO(raw_text))
    result: dict[str, AirlineEnrichment] = {}
    for row in reader:
        if len(row) < 5:
            continue
        iata = row[3].strip().upper()
        icao = row[4].strip().upper()
        if not iata or iata == "\\N":
            continue
        result[iata] = AirlineEnrichment(
            name=row[1].strip(),
            iata=iata,
            icao="" if icao == "\\N" else icao,
        )
    return result


@transaction.atomic
def persist_rows(
    rows: list[NormalizedFlightOffer],
    *,
    mark_stale_unpublished: bool,
) -> tuple[int, int, int]:
    created = 0
    updated = 0
    active_offer_ids = {row.provider_offer_id for row in rows}
    print(f"[seed] persisting {len(rows)} rows into flight_offers", flush=True)

    for index, row in enumerate(rows, start=1):
        defaults = {
            "listing_code": row.listing_code,
            "source_label": row.source_label,
            "origin_iata": row.origin_iata,
            "origin_airport_name": row.origin_airport_name,
            "origin_city": row.origin_city,
            "origin_state": row.origin_state,
            "destination_iata": row.destination_iata,
            "destination_airport_name": row.destination_airport_name,
            "destination_city": row.destination_city,
            "destination_state": row.destination_state,
            "departure_date": row.departure_date,
            "departure_at": row.departure_at,
            "arrival_at": row.arrival_at,
            "airline_code": row.airline_code,
            "airline_name": row.airline_name,
            "flight_number": row.flight_number,
            "cabin_class": row.cabin_class,
            "stops": row.stops,
            "refundable": row.refundable,
            "baggage_summary": row.baggage_summary,
            "fare_brand": row.fare_brand,
            "currency": row.currency,
            "total_amount": row.total_amount,
            "offer_expires_at": row.offer_expires_at,
            "metadata": row.metadata,
            "is_published": True,
        }
        _, was_created = FlightOffer.objects.update_or_create(
            provider=row.provider,
            provider_offer_id=row.provider_offer_id,
            defaults=defaults,
        )
        if was_created:
            created += 1
        else:
            updated += 1

        if index % 100 == 0 or index == len(rows):
            print(
                f"[seed] progress {index}/{len(rows)} persisted "
                f"(created={created}, updated={updated})",
                flush=True,
            )

    unpublished = 0
    if mark_stale_unpublished:
        unpublished = FlightOffer.objects.filter(provider=AVIATIONSTACK_PROVIDER, is_published=True).exclude(
            provider_offer_id__in=active_offer_ids
        ).update(is_published=False)
        print(f"[seed] marked {unpublished} stale rows unpublished", flush=True)

    return created, updated, unpublished


if __name__ == "__main__":
    raise SystemExit(main())
