# Flight Support Implementation Plan

## Goal

Add India-only flight search and booking support without increasing regression risk in the existing entertainment flow.

We will:

- keep flights separate from the current movies/sports backend flow
- use the same frontend chat shell
- use a separate flight domain flow underneath
- start with seeded India-only flight data
- use a single denormalized `flight_offers` table for the MVP

We will not:

- merge flights into the current entertainment search/booking orchestration
- normalize airports, airlines, and routes into separate tables yet
- introduce live inventory refresh or schedule-change handling in v1

## Product Decision

### Frontend

Use the same chat view for both entertainment and flights.

That means:

- one shared chat shell
- one shared thread list
- domain-specific rendering inside the thread

### Backend

Keep flight flow separate from entertainment flow.

That means:

- separate backend app for flights
- separate search services
- separate flight prompts / orchestration
- separate flight booking logic
- no expansion of the current entertainment domain flow beyond a top-level route or mode selection

### Thread Mode

Each thread should have a dominant domain mode:

- `entertainment`
- `flights`

The frontend chat shell stays shared, but thread behavior should remain domain-specific.

## MVP Scope

### In scope

- India-only seeded flight offers
- one denormalized `flight_offers` table
- flight search API
- flight result cards in frontend
- separate flight chat orchestration
- simulated flight booking flow
- passenger info collection suitable for MVP domestic booking

### Out of scope for now

- live price refresh
- real booking confirmation with suppliers
- cancellation / reschedule APIs
- international routes
- multi-city itineraries
- return-trip complexity unless explicitly included in seed/search design
- schema normalization into airport / airline / route reference tables

## Architecture Overview

### Existing apps to preserve

- `backend/apps/events`
- `backend/apps/agents`
- `backend/apps/bookings`

These should continue serving the entertainment flow only.

### New apps to add

- `backend/apps/flights`
- optionally later: `backend/apps/flight_agents`
- optionally later: `backend/apps/flight_bookings`

For v1, we can keep the flight conversational orchestration in `apps/flights` if that is simpler.

## Data Model

### New model: `FlightOffer`

Create a single denormalized table to store seeded India-only offers.

Suggested fields:

- `listing_code`
- `provider`
- `provider_offer_id`
- `source_label`
- `origin_iata`
- `origin_airport_name`
- `origin_city`
- `origin_state`
- `destination_iata`
- `destination_airport_name`
- `destination_city`
- `destination_state`
- `departure_date`
- `departure_at`
- `arrival_at`
- `airline_code`
- `airline_name`
- `flight_number`
- `cabin_class`
- `stops`
- `refundable`
- `baggage_summary`
- `fare_brand`
- `currency`
- `total_amount`
- `offer_expires_at`
- `is_published`
- `metadata`
- `created_at`
- `updated_at`

### Suggested indexes

- `origin_city + destination_city + departure_date`
- `origin_iata + destination_iata + departure_date`
- `airline_name`
- `departure_at`
- `listing_code`
- `is_published`

## Seed Strategy

### Data source approach

Use a combined-source seeding pipeline, but normalize everything into `flight_offers`.

Recommended MVP source mix:

- `Aviationstack` as the primary source for India domestic schedule-like flight rows
- `OpenFlights` as a secondary enrichment source for airport and airline naming consistency
- optional later: `Amadeus` or `Duffel` if we want richer offer-style or pricing-aware data

Recommended MVP pipeline:

1. Aviationstack adapter fetches India-relevant flights, routes, or timetable data
2. filter to India-only domestic routes
3. enrich missing airport or airline labels from OpenFlights when useful
4. normalize into the `FlightOffer` schema
5. store raw source payload in `metadata`

### Why this source mix

`Aviationstack` is a good fit for the first seeded MVP because it provides schedule-oriented aviation data that is enough to populate a searchable domestic flight inventory.

`OpenFlights` is useful as a lightweight reference dataset for airport and airline metadata, but it should not be the primary seeded inventory source because it is better suited to static reference enrichment than user-facing flight offer rows.

We should treat this first seeded dataset as searchable inventory snapshots, not live offer truth.

### Source responsibilities

#### Aviationstack

Use Aviationstack for fields such as:

- `origin_iata`
- `origin_airport_name`
- `origin_city`
- `destination_iata`
- `destination_airport_name`
- `destination_city`
- `airline_code`
- `airline_name`
- `flight_number`
- `departure_at`
- `arrival_at`
- `departure_date`

#### OpenFlights

Use OpenFlights as optional enrichment for:

- airport names when provider labels are incomplete
- airline naming consistency
- route sanity checks during seed QA

Do not depend on OpenFlights as the main inventory source for seeded search rows.

### India-only filter

Seed only domestic routes where both endpoints are in India.

Suggested initial city scope:

- Delhi
- Mumbai
- Bengaluru
- Hyderabad
- Chennai
- Kolkata
- Pune
- Ahmedabad
- Goa
- Kochi

### Management commands

Add commands under `backend/apps/flights/management/commands/`:

- `seed_flight_offers`
- `refresh_flight_offers`
- optional: `clear_flight_offers`

### Seed command behavior

The seed command should:

- fetch rows from the configured source adapters
- apply India-only domestic filtering
- enrich with OpenFlights metadata when available
- normalize them to `FlightOffer`
- upsert by `provider + provider_offer_id` or `listing_code`
- mark stale offers unpublished or replace the full seeded set

### Provider adapter design

For MVP, keep adapters small and isolated:

- `AviationstackSeedAdapter`
- optional later: `AmadeusSeedAdapter`
- optional later: `DuffelSeedAdapter`

Each adapter should:

- fetch raw upstream data
- map it into one normalized intermediate shape
- return rows ready for `FlightOffer` persistence

This keeps the denormalized table stable even if we change sources later.

## Backend Services

### Search service

Add `search_flight_offers(...)` in `backend/apps/flights/services.py`.

Supported filters should include:

- `origin_city`
- `destination_city`
- `departure_date`
- optional `departure_date_from` / `departure_date_to`
- `airlines`
- `cabin_classes`
- `stops`
- `price_min`
- `price_max`

### Serialization

Create a normalized flight result serializer for chat and API responses.

Suggested result payload:

- `listing_code`
- `origin_city`
- `origin_iata`
- `destination_city`
- `destination_iata`
- `departure_date`
- `departure_at`
- `arrival_at`
- `airline_name`
- `airline_code`
- `flight_number`
- `cabin_class`
- `stops`
- `currency`
- `total_amount`
- `refundable`
- `baggage_summary`

## API Design

### New endpoints

Add a separate flights API surface:

- `GET /api/flights/search/`
- `GET /api/flights/tools/origins/`
- `GET /api/flights/tools/destinations/`
- `GET /api/flights/tools/airlines/`
- `GET /api/flights/tools/cabin-classes/`

### Keep booking separate

Do not extend the current entertainment booking endpoint immediately.

For MVP, add flight-specific booking endpoints later if needed, for example:

- `POST /api/flights/bookings/select/`
- `POST /api/flights/bookings/confirm/`

or route those through a flight-specific chat flow first.

## Chat / Agent Design

### Shared shell, separate orchestration

The frontend chat shell remains shared, but backend routing should decide thread mode early:

- entertainment thread
- flight thread

### New flight conversational flow

Build a separate flight flow rather than expanding the current entertainment planner.

Suggested stages:

1. route intent to flight mode
2. resolve flight filters
3. search seeded offers
4. show flight results
5. select a flight
6. confirm the selected flight
7. collect passenger details
8. create simulated booking

### Flight filters to support

For v1:

- origin city
- destination city
- departure date
- airline
- cabin class
- direct / stops

### Booking info fields

Keep this separate from entertainment booking requirements.

Suggested MVP passenger fields:

- passenger full name
- email
- contact number

Add more fields later only if required.

## Frontend Plan

### Shared chat shell

Keep the existing chat shell and thread list.

### Add thread mode awareness

Each thread should know whether it is:

- `entertainment`
- `flights`

### Flight result card

Add a dedicated flight card UI with:

- origin -> destination
- date/time
- airline + flight number
- cabin class
- stops
- price
- refundable indicator

### Booking state UI

During flight booking:

- hide other suggestions while selection is active
- keep the selected flight visible
- collect passenger info in the same conversational pattern as events

## Phased Delivery

### Phase 1: Data foundation

- create `apps/flights`
- add `FlightOffer` model + migration
- add search service
- add seed command
- seed India-only data
- verify raw search API

### Phase 2: Flight search UI

- add flight search endpoint
- add frontend flight result card
- add thread mode support
- verify search-only flow

### Phase 3: Flight conversation flow

- add flight-specific filter resolution
- add thread-level flight chat orchestration
- verify same chat shell works with separate flight mode

### Phase 4: Simulated flight booking

- add flight selection
- add passenger info collection
- add simulated booking confirmation
- verify no regression in entertainment flow

## Verification Strategy

### Regression priority

Entertainment flow must remain stable throughout.

Required checks after each phase:

- movie search
- sports search
- entertainment booking
- off-track redirection
- flight search
- flight selection / booking once added

### Data verification

For seed quality:

- all rows are India-only
- origin and destination are populated
- price, airline, and departure fields are present
- listing codes are unique

### Manual verification

We should add a separate manual checklist later:

- `MANUAL_FLIGHT_VERIFICATION_GUIDE.md`

## Risks

### Main risks

- letting flights leak into entertainment prompts
- overloading the current `ActiveFilters` / planner model
- seeding inconsistent provider data into a denormalized table
- coupling flight booking requirements to entertainment booking requirements

### Mitigations

- separate apps and services
- separate thread mode
- separate prompts
- denormalized but explicit schema
- provider raw payload preserved in `metadata`

## Recommendation

The clean MVP path is:

1. separate flight app
2. one denormalized India-only `flight_offers` table
3. seed from provider-backed sources
4. build a separate flight flow
5. keep the same frontend chat shell
6. keep entertainment untouched as much as possible

## Immediate Next Step

Start with Phase 1:

- scaffold `backend/apps/flights`
- define `FlightOffer`
- add migration
- implement a seed command for India-only offers
- add a simple `search_flight_offers(...)` service
