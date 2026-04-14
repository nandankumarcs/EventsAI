#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import requests

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402
from django.conf import settings  # noqa: E402
from django.db import transaction  # noqa: E402

django.setup()

from apps.flights.models import FlightOffer  # noqa: E402
from scripts.flights.seed_offers import load_openflights_reference_data  # noqa: E402
from scripts.flights.seed_offers import INDIA_AIRPORTS  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Canonicalize flight airport and airline labels using OpenFlights without hitting Aviationstack."
    )
    parser.add_argument("--dry-run", action="store_true", help="Show what would change without writing to the database.")
    parser.add_argument(
        "--provider",
        default="aviationstack",
        help="Restrict updates to a specific provider (default: aviationstack).",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    timeout = float(getattr(settings, "AVIATIONSTACK_TIMEOUT_SECONDS", 20.0))
    session = requests.Session()
    session.timeout = timeout
    airport_map, airline_map = load_openflights_reference_data(session=session)
    print(f"[labels] loaded references: airports={len(airport_map)} airlines={len(airline_map)}", flush=True)

    queryset = FlightOffer.objects.all()
    if args.provider:
        queryset = queryset.filter(provider=args.provider)

    changed = 0
    updates = []
    for offer in queryset.iterator(chunk_size=500):
        next_origin_airport_name = offer.origin_airport_name
        next_origin_city = offer.origin_city
        next_destination_airport_name = offer.destination_airport_name
        next_destination_city = offer.destination_city
        next_airline_name = offer.airline_name

        origin_ref = airport_map.get((offer.origin_iata or "").upper())
        destination_ref = airport_map.get((offer.destination_iata or "").upper())
        airline_ref = airline_map.get((offer.airline_code or "").upper())

        if origin_ref:
            next_origin_airport_name = origin_ref.name
        if destination_ref:
            next_destination_airport_name = destination_ref.name
        if airline_ref and airline_ref.name:
            next_airline_name = airline_ref.name

        # Keep canonical MVP city labels from our India airport mapping.
        origin_map = INDIA_AIRPORTS.get((offer.origin_iata or "").upper())
        destination_map = INDIA_AIRPORTS.get((offer.destination_iata or "").upper())
        if origin_map:
            next_origin_city = origin_map["city"]
        if destination_map:
            next_destination_city = destination_map["city"]

        if (
            next_origin_airport_name != offer.origin_airport_name
            or next_origin_city != offer.origin_city
            or next_destination_airport_name != offer.destination_airport_name
            or next_destination_city != offer.destination_city
            or next_airline_name != offer.airline_name
        ):
            changed += 1
            if not args.dry_run:
                offer.origin_airport_name = next_origin_airport_name
                offer.origin_city = next_origin_city
                offer.destination_airport_name = next_destination_airport_name
                offer.destination_city = next_destination_city
                offer.airline_name = next_airline_name
                updates.append(offer)

    if args.dry_run:
        print(f"[labels] dry run complete: {changed} rows would be updated.")
        return 0

    if not updates:
        print("[labels] no rows needed canonicalization.")
        return 0

    with transaction.atomic():
        FlightOffer.objects.bulk_update(
            updates,
            ["origin_airport_name", "origin_city", "destination_airport_name", "destination_city", "airline_name"],
            batch_size=500,
        )
    print(f"[labels] canonicalized {changed} rows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
