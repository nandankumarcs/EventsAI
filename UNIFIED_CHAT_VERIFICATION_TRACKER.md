# Unified Chat Verification Tracker (Flights + Entertainment)

## Scope

Verify the end-to-end behavior of the unified chat entrypoint and shared shell across both domains:

- Entertainment search and booking (existing behavior)
- Flights search and simulated booking (new behavior)
- Seamless mode switching mid-thread (new behavior)

Order of operations:

1. API verification (positive cases)
2. API verification (negative cases)
3. Browser verification (positive cases)
4. Browser verification (negative cases)

## Environment

- Backend base URL: `http://127.0.0.1:3003`
- Frontend base URL: `http://127.0.0.1:5173`

## Preconditions

- Backend migrations applied
- Seeded datasets present
  - entertainment seed OK
  - `flight_offers` seeded (expected non-zero)
- Backend env configured for LLM resolver/router

## API Verification

### Conventions

- All chat turns go through: `POST /api/chats/chat/`
- Payload shape:

```json
{
  "message": "...",
  "thread_id": "... optional ..."
}
```

- Expected response top-level keys:
  - `thread`
  - `assistant_message`
  - `active_filters`
  - `search_domains`
  - `results_by_domain`
  - `latest_result_context`
  - `pending_booking`
  - `needs_clarification`
  - `clarification_question`

### A) Positive cases (API)

#### A1) Create thread (unknown mode)

- **Request**: `POST /api/chats/threads/` with body `{ "title": "Unified verification" }`
- **Expected**:
  - `thread.mode == "unknown"`
  - filter state exists (implicit)

- **Track**:
  - Thread ID:
  - Result: PASS/FAIL
  - Notes:

#### A2) Unknown → Flights routing (mode persisted)

- **Request**: `POST /api/chats/chat/` with `thread_id` from A1 and message:
  - `"I need a flight from Delhi to Mumbai on 22 April"`
- **Expected**:
  - `thread.mode == "flights"`
  - `search_domains == ["flights"]` (unless clarification)
  - `results_by_domain.flights` exists when results found
  - `assistant_message.metadata.results_by_domain.flights` exists when results found

- **Track**:
  - Result: PASS/FAIL
  - Notes:

#### A3) Flights: refine filters in same thread

- **Request**: message like:
  - `"Only Indigo, economy"`
- **Expected**:
  - still `thread.mode == "flights"`
  - results update and `latest_result_context` updates

- **Track**:
  - Result: PASS/FAIL
  - Notes:

#### A4) Flights: select a flight from results

- **Request**: message like:
  - `"Select option 1"` or `"Book the first one"`
- **Expected**:
  - `pending_booking.listing_code` present
  - `assistant_message.metadata.booking_action` indicates selection pending / awaiting info
  - results carousel hidden behavior is UI; API should still include pending booking

- **Track**:
  - Selected listing_code:
  - Result: PASS/FAIL
  - Notes:

#### A5) Flights: complete passenger info and confirm

- **Request sequence** (example):
  - `"yes"` (if confirmation step exists)
  - `"My name is Rahul Sharma"`
  - `"rahul@example.com"`
  - `"9876543210"`
  - `"confirm"`

- **Expected**:
  - booking confirmed response contains booking reference in metadata (implementation-specific)
  - `thread.status == "booked"`

- **Track**:
  - Booking reference:
  - Result: PASS/FAIL
  - Notes:

#### A6) Seamless mode switch: Flights → Entertainment (same thread)

- **Request**: message like:
  - `"Now show movies in Mumbai this weekend"`
- **Expected**:
  - `thread.mode == "entertainment"` (only if router confidence threshold met)
  - `ThreadFilter` state cleared on switch (active_filters/results/pending_booking reset) before entertainment turn persists its own state
  - entertainment response contains appropriate `results_by_domain` (movies/sports)

- **Track**:
  - Result: PASS/FAIL
  - Notes:

#### A7) Seamless mode switch back: Entertainment → Flights

- **Request**:
  - `"Actually find me a flight Bangalore to Goa on 24 April"`
- **Expected**:
  - `thread.mode == "flights"` (if confident)
  - flight results returned

- **Track**:
  - Result: PASS/FAIL
  - Notes:

### B) Negative cases (API)

#### B1) Validation: empty message

- **Request**: `POST /api/chats/chat/` with `{ "message": "" }`
- **Expected**: `400` with `{ "error": "message is required" }`

- **Track**:
  - Result: PASS/FAIL
  - Notes:

#### B2) Invalid thread_id

- **Request**: `POST /api/chats/chat/` with random UUID thread_id
- **Expected**: `404` JSON error (implementation-specific)

- **Track**:
  - Result: PASS/FAIL
  - Notes:

#### B3) Flights: confirm without selection

- **Setup**: ensure thread in flights mode with results but no selection
- **Request**: `"confirm"`
- **Expected**:
  - no crash
  - clarification-style response (`needs_clarification == true` or booking action no_match)

- **Track**:
  - Result: PASS/FAIL
  - Notes:

#### B4) Flights: passenger field misalignment guard

- **Setup**: pending booking awaiting `email`
- **Request**: send a name while awaiting email
- **Expected**:
  - system keeps awaiting email (state-enforced)
  - does not incorrectly store name in email

- **Track**:
  - Result: PASS/FAIL
  - Notes:

#### B5) Mode switching: low confidence should not switch

- **Setup**: thread in flights mode
- **Action**: message that is ambiguous, and force router low confidence (observed)
- **Expected**:
  - no mode change
  - continues in current mode

- **Track**:
  - Result: PASS/FAIL
  - Notes:

#### B6) Thread status: booked thread rejects new turns

- **Setup**: a thread with `status == booked`
- **Request**: any new message
- **Expected**: `409` with error message about read-only thread

- **Track**:
  - Result: PASS/FAIL
  - Notes:

## Browser Verification

### C) Positive cases (Browser)

#### C1) Thread mode badge updates on routing

- Create new thread
- Send a flight query
- **Expected**:
  - header shows mode badge `flights`

- Track: PASS/FAIL

#### C2) Flights booking UI behavior (shared shell)

- Search flights
- Select a flight
- **Expected**:
  - pending booking card visible
  - results carousel hidden while selection active

- Track: PASS/FAIL

#### C3) Mode switch in UI feels seamless

- In same thread, after flight interaction, ask for movies/sports
- **Expected**:
  - mode badge updates to `entertainment`
  - results render as entertainment cards

- Track: PASS/FAIL

### D) Negative cases (Browser)

#### D1) Booked thread read-only banner

- After booking, attempt to send a new message
- **Expected**:
  - UI prevents send or shows error

- Track: PASS/FAIL

#### D2) Robustness: refresh page mid-conversation

- During pending selection or awaiting user info, refresh
- **Expected**:
  - pending booking section still visible
  - state restored from thread detail

- Track: PASS/FAIL

## Results Summary

- Date:
- Backend commit SHA:
- Overall API Positive: PASS/FAIL
- Overall API Negative: PASS/FAIL
- Overall Browser Positive: PASS/FAIL
- Overall Browser Negative: PASS/FAIL

## Findings / Follow-ups

- Item:
  - Severity:
  - Owner:
  - Notes:
