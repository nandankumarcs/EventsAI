# Flight Implementation Log

## 2026-04-14 - Phase 2/3 kickoff

### Intent and constraints

- Continue beyond seeding into the next implementation phase from the flight plan.
- Keep entertainment and flight orchestration separate to reduce regression risk.
- Use LLM-driven intent capture and filter extraction; avoid heuristic intent routing.
- Maintain a running log to enable clean handoff in a new chat without gaps.

### What was implemented

1. Added thread mode support at the chat model layer.
- `ChatThread.mode` now supports: `unknown`, `entertainment`, `flights`.
- Default is `unknown` for new threads created via chat thread APIs.

2. Added unified chat routing endpoint and service.
- New endpoint: `POST /api/chats/chat/`
- New service: `apps/chats/services.py`
- Behavior:
  - for `unknown` threads, LLM router decides mode (`flights` or `entertainment`)
  - delegates to flight chat flow or existing entertainment flow
  - persists chosen mode on the thread

3. Added separate flight chat orchestration service.
- New file: `apps/flights/chat_services.py`
- Uses LLM resolver from `apps/flights/langchain_tools.py` to capture flight filters.
- Searches only `flight_offers` and returns `results_by_domain.flights`.
- Persists flight filter state and latest flight result context in `ThreadFilter`.

4. Added flight resolver schemas and prompt chain.
- New schema file: `apps/flights/schemas.py`
- New LLM resolver file: `apps/flights/langchain_tools.py`
- Resolver consumes:
  - current filters
  - user message
  - origin/destination/airline/cabin catalogs
- Returns structured `FlightFilterResolution`.

5. Updated frontend API contract for unified routing and flight domain.
- `sendChatMessage` now calls `/api/chats/chat/` instead of `/api/agents/chat/`.
- Added thread `mode` to API types.
- Added `flights` to `SearchResultsByDomain`.
- Extended result item typing for flight fields.

6. Updated chat result cards for flight rendering.
- Flight cards now render route, airline/flight number, cabin/stops, and departure datetime in the shared chat shell.

7. Improved standalone seeding robustness and observability.
- Added detailed progress logs in `backend/scripts/flights/seed_offers.py`.
- Added fallback from batched origin fetch to single-origin fetch when provider rejects batched iata.
- Added payload-shape guards to avoid crashes on malformed provider data.
- Added separate label canonicalization script:
  - `backend/scripts/flights/canonicalize_labels.py`
  - canonicalizes existing rows without consuming Aviationstack quota.

### Key provider observations

- Aviationstack `flightsFuture` request with comma-separated `iataCode` is rejected with `400` for current account/endpoint behavior.
- Script now degrades safely to single-origin requests with clear logs.

### Current seeded dataset snapshot

- Total rows in `flight_offers`: `3306`
- Departure date spread:
  - `2026-04-22` (833)
  - `2026-04-23` (646)
  - `2026-04-24` (664)
  - `2026-05-03` (317)
  - `2026-05-10` (317)
  - `2026-05-17` (317)
  - `2026-05-24` (212)

### Remaining for next iteration

- Verify end-to-end unified chat behavior in browser for both thread modes.
- Add explicit flight thread-mode tests at API boundary (`/api/chats/chat/`) without mocks where feasible.
- Add flight sidebar/filter panel awareness for better UX in shared shell.
- Add simulated flight booking flow (selection, confirmation, passenger info) in a separate flight booking track.

## 2026-04-14 - Phase 4 implementation (simulated flight booking)

### What was added

1. Separate flight booking persistence model.
- Added `FlightBooking` model in `backend/apps/flights/models.py`.
- Added migration `backend/apps/flights/migrations/0002_flightbooking.py`.
- Flight bookings are stored separately from entertainment bookings and linked to `ChatThread`.

2. Separate flight booking service layer.
- Added `backend/apps/flights/booking_services.py`.
- Responsibilities:
  - pending selection state management (`select`, `clear`)
  - passenger info capture + validation (`name`, `email`, `contact_number`)
  - missing-field progression
  - simulated booking creation with `booking_reference`
  - thread status transition to `booked` when confirmed

3. LLM structured-output booking turn resolver (no heuristic intent switching).
- Added `FlightBookingTurnResolution` and related schemas in `backend/apps/flights/schemas.py`.
- Added `resolve_flight_booking_turn(...)` in `backend/apps/flights/langchain_tools.py`.
- The booking resolver now handles:
  - selection/change selection from latest shown results
  - explicit clear/cancel
  - passenger-info capture
  - confirmation path
  - soft redirect while keeping current selection

4. Flight chat orchestration upgraded to include booking stage.
- Reworked `backend/apps/flights/chat_services.py` to process booking actions before filter search.
- Behavior:
  - if selection is active, suggestions remain hidden
  - off-track message keeps selection and soft-redirects
  - explicit clear restores search results from active filters
  - user can change selected flight during info collection
  - confirmation is blocked until required passenger fields are complete

5. Frontend compatibility updates.
- Updated flight pending/selected card normalization in:
  - `frontend/src/components/chat/chat-workspace.tsx`
- Updated shared API typing for flight context fields in:
  - `frontend/src/lib/api.ts`

### Gaps found during live API verification and fixes

1. Gap: runtime error when LLM returned confirmation/user-info action before a valid selection existed.
- Fix: wrapped booking action execution with safe fallbacks in `chat_services.py` and downgraded to `no_match` clarification response instead of raising.

2. Gap: passenger field misalignment (LLM occasionally mapped a name into email field).
- Fix A: prompt tightening in `resolve_flight_booking_turn(...)` to force `requested_field == pending_booking.awaiting_field` when awaiting field exists.
- Fix B: state-enforced capture in `chat_services.py` to prioritize `pending_booking.awaiting_field` over model-provided field name.

### Verification performed

1. Backend tests:
- `./.venv/bin/python manage.py test apps.chats apps.flights --keepdb`
- Result: pass (`18` tests)

2. Frontend compile/build:
- `npm run build` (in `frontend`)
- Result: pass

3. Live API smoke verification on local server:
- Started backend: `.venv/bin/python manage.py runserver 3003`
- Verified flight flow end-to-end:
  - search -> select -> distraction -> selection remains
  - confirm -> name -> email -> contact number -> booking confirmed
  - thread status transitions to `booked`
  - booking reference returned in assistant metadata
  - changing selected flight before confirmation updates pending selection

### Current status after this phase

- Phase 4 core is now implemented in separate flight flow with LLM-based turn resolution.
- Entertainment flow remains isolated and untouched.
- Remaining follow-up is mostly UX/verification docs expansion and optional flight booking listing APIs.
