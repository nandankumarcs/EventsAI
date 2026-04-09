# Full Verification Plan

## Objective

Validate every implemented MVP feature in Attend across backend, agents, database, frontend, and browser flows.

This plan is intended to be exhaustive enough for:

- pre-release regression testing
- phase-close verification
- future iteration sanity checks

## Verification Principles

- verify deterministic backend behavior before UI behavior
- verify agent resolution behavior before end-to-end journeys
- verify both happy paths and failure paths
- verify persistence after refresh, reload, and thread switching
- verify that the assistant never returns results outside the deterministic query layer
- verify that all categorical filters used by agents come from DB-backed tools

## Environments

### Required

- backend running on `http://127.0.0.1:8000`
- frontend running on `http://127.0.0.1:4173`
- PostgreSQL reachable
- seeded future-only data present
- valid OpenAI API key configured

### Recommended Reset Before Full Pass

```bash
cd /Users/mac/Documents/attend-poc/backend
.venv/bin/python manage.py seed_event_data --reset
```

## Preflight Checks

Run these before scenario testing:

### Backend

```bash
cd /Users/mac/Documents/attend-poc/backend
.venv/bin/python manage.py check
.venv/bin/python manage.py test apps.chats apps.bookings apps.agents apps.events --keepdb
```

### Frontend

```bash
cd /Users/mac/Documents/attend-poc/frontend
npm run lint
npm run build
```

### Health

- `GET /api/health/` returns `status: ok`
- database reports `reachable: true`

## Verification Areas

1. Foundation and environment
2. Database schema and seed quality
3. Deterministic search layer
4. DB-backed filter tools
5. Agent orchestration and thread filter state
6. Chat persistence
7. Booking flow
8. Frontend UX
9. End-to-end user journeys
10. Failure and recovery flows

## 1. Foundation And Environment

### Scenario 1.1

- start backend
- start frontend
- load app in browser
- expected:
  - no startup errors
  - no broken imports
  - app renders sidebar and main chat area
  - health badges render correctly

### Scenario 1.2

- restart backend while frontend is open
- expected:
  - app recovers after retry
  - no permanent broken state

## 2. Database Schema And Seed Quality

### Scenario 2.1 Table existence

Verify these tables exist:

- `movie_events`
- `sport_events`
- `chat_threads`
- `chat_messages`
- `thread_filters`
- `bookings`

### Scenario 2.2 Seed volume

Verify:

- movies seeded in meaningful volume
- sports seeded in meaningful volume
- both domains have multiple cities and venues

### Scenario 2.3 Future-only data

Verify:

- no movie event date is in the past
- no sport event date is in the past

### Scenario 2.4 Variety checks

Verify distinct values exist for:

- movie cities
- movie genres
- movie languages
- movie directors
- movie formats
- sport cities
- sport types
- sport tournaments
- sport format labels
- sport organizers

### Scenario 2.5 Duplicate quality

Verify:

- no bad duplicate rows by listing code
- movie listings do not feel artificially repeated in the same city/date combination

## 3. Deterministic Search Layer

### Movie search scenarios

#### Scenario 3.1 Single filter by city

- call movie search with `cities`
- expected:
  - only movies in that city returned

#### Scenario 3.2 Single filter by genre

- call movie search with `genres`
- expected:
  - only matching genres returned

#### Scenario 3.3 Single filter by director

- call movie search with `directors`
- expected:
  - only matching director rows returned

#### Scenario 3.4 Multiple filters narrow correctly

- use `cities + genres + languages + formats`
- expected:
  - results are a strict narrowed subset

#### Scenario 3.5 Empty result

- use an impossible combination
- expected:
  - `count = 0`
  - `results = []`

### Sport search scenarios

#### Scenario 3.6 Single filter by sport type

- call sport search with `sport_types`
- expected:
  - only that sport type returned

#### Scenario 3.7 Team filter

- call sport search with `teams`
- expected:
  - matches if team appears as home or away

#### Scenario 3.8 Season and organizer filter

- call sport search with `season_labels + organizers`
- expected:
  - only matching sport events returned

#### Scenario 3.9 Time range

- call sport search with `start_time_from + start_time_to`
- expected:
  - only matching time window returned

#### Scenario 3.10 Pagination

- call with `limit` and `offset`
- expected:
  - page boundaries work consistently

## 4. DB-Backed Filter Tools

### Scenario 4.1 Event type catalog

- `GET /api/events/tools/event-types/`
- expected:
  - values reflect actual DB availability

### Scenario 4.2 Movie tool coverage

Verify these endpoints return values:

- locations
- languages
- genres
- cast members
- directors
- certifications
- titles
- venues
- formats
- franchises
- content origins

### Scenario 4.3 Sport tool coverage

Verify these endpoints return values:

- locations
- sport types
- tournaments
- season labels
- competition stages
- format labels
- home teams
- away teams
- teams
- participant names
- venues
- featured athletes
- organizers
- match numbers

### Scenario 4.4 Temporal normalization

Verify:

- `this sunday`
- `this sunday or monday`
- `next weekend`
- `monday evening`
- `around 7pm`
- `today`
- `tomorrow`

Expected:

- canonical dates
- correct time windows
- no malformed timestamps

## 5. Agent Orchestration And Thread Filter State

### Scenario 5.1 Add first filter

User:

`I like sports`

Expected:

- thread created
- `event_types = ["sports"]`
- sports search runs

### Scenario 5.2 Add follow-up filter

User sequence:

- `I like sports`
- `I want to watch something on sunday`

Expected:

- second turn preserves `event_types`
- adds `event_dates`

### Scenario 5.3 Replace filter

User sequence:

- `sports in Delhi`
- `actually Mumbai`

Expected:

- `cities` changes from old value to new value
- other filters remain intact

### Scenario 5.4 Domain switch

User sequence:

- `Show me cricket in Mumbai`
- `Show movies instead`

Expected:

- `event_types` switches to `movies`
- sports-only filters are cleared
- shared filters like `cities` may remain

### Scenario 5.5 No-match categorical resolution

User:

`Show me handball in Mumbai`

Expected:

- no deterministic search results returned
- assistant does not broaden to unrelated sports
- response asks for another compatible filter

### Scenario 5.6 Ambiguous resolution

User:

`Show me sports in Delhi`

Expected:

- if multiple canonical interpretations exist, assistant asks clarification
- no fabricated match selection

### Scenario 5.7 Tool-only canonical matching

Verify:

- categorical values persisted in `thread_filters` are canonical DB values only
- no hardcoded alias output is stored directly

### Scenario 5.8 Richer filter resolution

Verify chat turns can resolve:

- `movies directed by Christopher Nolan`
- `movies in IMAX 70mm`
- `movies with certification UA`
- `sports in IPL 2026`
- `sports by BCCI`

## 6. Chat Persistence

### Scenario 6.1 Thread creation

- create thread
- expected:
  - thread exists in DB
  - `thread_filters` row exists

### Scenario 6.2 Message order

- send multiple turns
- expected:
  - messages persist in order
  - positions increment correctly

### Scenario 6.3 Reload preservation

- refresh browser on active thread
- expected:
  - same thread loads
  - same messages render
  - same active filters render

### Scenario 6.4 Sidebar persistence

- create multiple threads
- switch between them
- refresh page
- expected:
  - sidebar still shows all threads
  - selected thread content is consistent

## 7. Booking Flow

### Scenario 7.1 Confirm booking from result card

- choose an available result
- click confirm
- expected:
  - booking row created
  - thread marked `booked`
  - assistant confirmation message saved
  - booking reference visible

### Scenario 7.2 Idempotent same booking

- repeat booking confirm on same thread and same listing
- expected:
  - no duplicate booking row
  - existing booking returned

### Scenario 7.3 Reject new booking on booked thread

- confirm one result
- try to confirm a different listing in same booked thread
- expected:
  - rejected

### Scenario 7.4 Persistence after refresh

- refresh booked thread
- expected:
  - thread remains booked
  - confirmation message remains
  - result cards show booking as saved

## 8. Frontend UX

### Scenario 8.1 Empty state

- load app with no selected thread
- expected:
  - guidance copy visible
  - no layout breakage

### Scenario 8.2 Loading state

- select a different thread
- expected:
  - loading state appears cleanly

### Scenario 8.3 Error state

- force backend down
- expected:
  - health error banner shown
  - retry action shown

### Scenario 8.4 Retry connection

- load with backend down
- bring backend up
- click retry
- expected:
  - health badges recover
  - threads load

### Scenario 8.5 Retry send

- draft a message
- bring backend down
- send
- bring backend back
- click retry
- expected:
  - message is sent
  - thread updates correctly

### Scenario 8.6 Booked-thread UX

- confirm a booking
- expected:
  - composer replaced with read-only guidance
  - new thread CTA shown
  - no dead end

### Scenario 8.7 Desktop layout

- verify at desktop width
- expected:
  - sidebar and main panel readable
  - no overlap or clipped content

### Scenario 8.8 Mobile layout

- verify at mobile width
- expected:
  - no broken cards
  - no unusable buttons
  - content remains scrollable

## 9. End-To-End User Journeys

### Scenario 9.1 Progressive sports narrowing

User sequence:

- `I want sports`
- `in Mumbai`
- `this sunday`
- `around 7pm`
- `cricket`

Expected:

- filters accumulate in thread state
- results narrow progressively

### Scenario 9.2 Progressive movie narrowing

User sequence:

- `Show me movies`
- `in Pune`
- `directed by Christopher Nolan`
- `in IMAX 70mm`

Expected:

- all filter additions persist
- results narrow without losing prior filters

### Scenario 9.3 Correction journey

User sequence:

- `Show cricket in Delhi on sunday`
- `actually Mumbai`

Expected:

- city replaced
- date and domain preserved

### Scenario 9.4 No-match journey

User:

`Show handball in Mumbai`

Expected:

- no unrelated result cards
- clear next-step guidance

### Scenario 9.5 Booking completion journey

User:

- discovers result
- confirms booking
- refreshes page
- opens another thread

Expected:

- booking persists
- booked thread is read-only
- new thread starts cleanly

## 10. Failure And Recovery

### Scenario 10.1 OpenAI failure fallback

- simulate invalid or unavailable resolver response
- expected:
  - request does not 500
  - assistant returns stable fallback or no-input behavior

### Scenario 10.2 Database connectivity issue

- simulate DB unreachability
- expected:
  - health endpoint reports degraded state
  - frontend shows clear failure state

### Scenario 10.3 Invalid payloads

Verify API error handling for:

- missing message
- invalid JSON
- missing booking inputs
- invalid listing code

### Scenario 10.4 Archived or booked thread mutation

Verify:

- booked threads reject new chat turns
- archived threads reject new chat turns

## Suggested Execution Order

1. Preflight checks
2. Database schema and seed validation
3. Deterministic search tests
4. Tool endpoint validation
5. Agent orchestration scenarios
6. Chat persistence scenarios
7. Booking scenarios
8. Frontend UX scenarios
9. End-to-end journeys
10. Failure and recovery scenarios

## Exit Criteria

The MVP verification pass is complete when:

- all automated checks pass
- all critical happy paths pass
- no dead-end states remain in browser flows
- no broad fallback happens after categorical no-match or ambiguity
- persisted filter state behaves correctly across follow-up messages
- booking flow is idempotent and thread-closing behavior works
- desktop and mobile widths are both usable
