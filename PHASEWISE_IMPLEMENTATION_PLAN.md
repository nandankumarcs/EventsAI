# Agentic BookMyShow MVP - Phase-wise Implementation Plan

## Product Goal

Build a chat-first event discovery and booking MVP inspired by BookMyShow, where users progressively apply and update filters through conversation instead of using a traditional filter UI.

The system should:

- support `movies` and `sports` in V1
- persist chat threads, chat messages, and thread-level filter state from day one
- use deterministic database filtering for event retrieval
- use LangChain agents to resolve user intent into normalized filter values
- simulate booking completion and save booking records in the database
- keep the UI centered around chat, with a left sidebar for past threads

## Core Principles

- MVP first: no overengineering
- clean project structure from the start
- deterministic event retrieval, not fuzzy final matching
- conversational filter accumulation and replacement per thread
- future-only seed data
- full verification after every phase

## Proposed Tech Stack

### Frontend

- React
- TypeScript
- Vite
- shadcn/ui
- chat-first layout

### Backend

- Django
- PostgreSQL
- LangChain for orchestration
- OpenAI API for model access

## High-level Architecture

### Event Retrieval Pattern

The final event fetch should always be deterministic:

1. user message arrives
2. main orchestration agent decides which filter resolvers are needed
3. mini resolver agents normalize user intent into canonical filter values
4. filter state for the thread is created, updated, or replaced in the database
5. deterministic fetch tool such as `get_movies` or `get_sports` runs with normalized filters
6. matched events are returned to the user

### Agent Pattern

- one main orchestration agent for conversation flow
- mini resolver agent per filter dimension
- each mini agent gets only the tools required for its dimension
- each mini agent returns structured output with:
  - success or failure
  - resolved values
  - optional reason when no match exists

### State Pattern

Each chat thread will persist:

- thread metadata
- messages
- active filter state
- booking actions taken in that thread

When a user changes their mind, only the related filter values are overwritten while the rest of the thread state remains intact.

## Suggested Data Domains For V1

### Event Types

- movies
- sports

### Likely Filter Dimensions

These should be implemented only where they make logical sense.

#### Shared/Common

- event type
- location city
- venue
- event date
- day of week
- time of day
- language
- price band
- tags

#### Movies

- title
- genre
- release date
- cast
- director
- certification
- format
- duration

#### Sports

- sport type
- tournament or league
- team names
- player names
- season

## Phase Plan

## Phase 1 - Project Foundation

### Objective

Create the base frontend and backend structure so the project is runnable and organized before domain logic begins.

### Scope

- initialize React frontend
- initialize Django backend
- add shared environment configuration
- set up PostgreSQL connection
- add shadcn/ui base setup
- create basic app layout shells for:
  - left thread sidebar
  - main chat panel
- create backend app/module boundaries for:
  - chats
  - events
  - bookings
  - agents

### Deliverables

- working frontend app
- working Django app
- database connection verified
- initial folder structure committed
- environment example files

### Verification

- frontend boots locally without broken routes
- backend boots locally without configuration errors
- frontend can talk to backend health endpoint
- no broken imports or startup errors

## Phase 2 - Database Schema And Seed Pipeline

### Objective

Create clean schema design for events, chats, filters, and bookings, then populate realistic future-only event data.

### Scope

- define PostgreSQL schema for:
  - `movie_events`
  - `sport_events`
  - `chat_threads`
  - `chat_messages`
  - `thread_filters`
  - `bookings`
- decide and implement filter-state storage shape
- create seed scripts for event data
- seed a few hundred future-only movie and sports records
- use mostly real-world reference data where practical, with synthetic augmentation where needed

### Suggested Schema Direction

Keep event tables separate as requested.

Keep thread filters simple and explicit for MVP.

Use one `thread_filters` record per thread with structured JSON for active filters because it keeps update logic simple and fits the conversational state model well.

### Seed Data Expectations

- all dates must be in the future
- enough variety to test partial and compound filtering
- rich columns for realistic conversations
- multiple cities and venues
- sports focused on cricket plus other sports for breadth
- movies with genre, cast, language, certification, and release metadata

### Verification

- migrations run cleanly
- tables are created with correct indexes and constraints
- seeded counts match target size
- spot checks confirm all events are future-dated
- distinct-value checks show enough variety for filter tools

## Phase 3 - Deterministic Query Layer

### Objective

Build the exact retrieval layer that behaves like a traditional filtered listing backend.

### Scope

- implement `get_movies` query path
- implement `get_sports` query path
- support multi-select arrays for filters
- support optional filters
- return stable, structured result payloads
- add pagination and result count if useful for chat responses

### Rules

- no LLM logic inside final retrieval
- exact deterministic filtering only
- one filter should broaden results appropriately
- more filters should narrow results appropriately

### Verification

- direct tests for each filter dimension
- direct tests for compound filters
- direct tests for empty result behavior
- direct tests for filter replacement behavior at thread level

## Phase 4 - Filter Value Tools And Resolver Contracts

### Objective

Create the tool surface that mini agents will use to normalize user intent into valid filter values.

### Scope

- implement distinct-value tools such as:
  - `get_all_event_types`
  - `get_available_movie_locations`
  - `get_available_sport_locations`
  - `get_available_sport_types`
  - `get_available_movie_languages`
  - `get_available_movie_genres`
  - `get_available_venues`
  - similar tools for other supported filter domains
- define structured response contract for resolver agents
- add utility logic for date resolution like:
  - this Sunday
  - next weekend
  - Monday evening
  - around 7pm

### Resolver Output Contract

Each resolver should return a predictable object such as:

- `status`
- `filter_key`
- `resolved_values`
- `message`
- `confidence` if helpful

### Verification

- unit tests for distinct-value tools
- unit tests for date and time normalization
- tests for no-match scenarios
- tests for alias mapping such as `Delhi` -> `New Delhi` when appropriate

## Phase 5 - LangChain Agent Orchestration

### Objective

Build the main agent and mini resolver agents using LangChain without introducing LangGraph yet.

### Scope

- create main orchestration agent
- create mini resolver agents by domain
- wire each mini agent only to its own tools
- define prompt rules for:
  - adding filters
  - replacing filters
  - preserving untouched filters
  - identifying insufficient input
  - returning helpful no-match responses
- orchestrate:
  - message intake
  - resolver execution
  - thread filter updates
  - final event fetch
- prepare structured backend response for frontend rendering

### Important Behavioral Rules

- current thread filter state is always loaded before processing the next message
- latest user message can add, replace, or remove constraints
- final event query runs on the merged current state
- agent should not hallucinate values outside tool outputs
- agent should prefer showing best possible results using current filters instead of asking early follow-up questions
- agent should ask clarifying questions only when:
  - the user intent maps to multiple incompatible meanings
  - a critical filter is required for a meaningful query
  - no results are found
  - the user explicitly appears undecided

### Verification

- simulated conversation tests
- correction tests like `actually Mumbai`
- domain switch tests like `show movies instead`
- fallback tests where no available values match user intent

## Phase 6 - Chat Persistence And Booking Flow Backend

### Objective

Persist conversations end to end and support simulated booking confirmation.

### Scope

- create thread create/list/detail APIs
- create message persistence flow
- persist thread filter state after each turn
- add booking confirmation flow
- create booking record table writes after explicit user confirmation
- include event snapshot or key metadata in booking record

### Verification

- thread history loads correctly
- messages persist in correct order
- filter state persists and updates correctly across turns
- booking rows are created only after confirmation
- repeated refresh does not lose state

## Phase 7 - Frontend Chat Experience

### Objective

Build the MVP user interface around chat-first discovery and booking.

### Scope

- left sidebar for past threads
- main chat conversation area
- chat input and send flow
- render assistant event results in a clean, scannable format
- booking confirmation interaction in chat
- loading, retry, and empty states
- simple thread switching behavior

### MVP UX Direction

- main view should feel like a concierge for events
- results should read like curated options, but remain grounded in deterministic filtering
- do not build the right-side applied-filters panel yet unless needed for debugging
- prepare the layout so that panel can be added later without major rework

### Verification

- browser verification for thread creation, chat, and thread switching
- responsive checks on desktop and mobile widths
- no layout breakage
- no dead-end states after no-match or booking confirmation

## Phase 8 - End-to-End Integration And Hardening

### Objective

Close gaps between backend, agents, database, and frontend to make the MVP reliable.

### Scope

- connect frontend chat to orchestration backend
- refine assistant response formatting
- improve error handling
- add logging where useful
- tighten prompts and tool contracts
- remove MVP rough edges that create confusion

### Verification

- end-to-end manual user journeys in browser
- conversation journeys for both movies and sports
- partial filter journey
- progressive narrowing journey
- filter replacement journey
- booking completion journey
- no-match journey

## Phase 9 - Cleanup, Docs, And Handoff

### Objective

Make the project clean, understandable, and ready for ongoing iteration.

### Scope

- code cleanup
- meaningful comments only where they help
- setup documentation
- local run instructions
- seed instructions
- environment setup documentation
- phase completion notes and known limitations

### Verification

- fresh setup instructions are accurate
- no dead files or unused scaffolding
- code structure remains easy to navigate

## Verification Standard For Every Phase

Every completed phase should include:

1. implementation review against phase scope
2. automated verification where possible
3. manual verification where needed
4. browser verification for UI-facing behavior
5. gap check before moving to the next phase

We should not advance a phase until the core acceptance criteria for that phase are satisfied.

## Recommended Delivery Order

1. Phase 1 - Project Foundation
2. Phase 2 - Database Schema And Seed Pipeline
3. Phase 3 - Deterministic Query Layer
4. Phase 4 - Filter Value Tools And Resolver Contracts
5. Phase 5 - LangChain Agent Orchestration
6. Phase 6 - Chat Persistence And Booking Flow Backend
7. Phase 7 - Frontend Chat Experience
8. Phase 8 - End-to-End Integration And Hardening
9. Phase 9 - Cleanup, Docs, And Handoff

## Current Open Decisions

These are not blockers for planning, but we should lock them before implementation begins.

- how many result cards to return in one response by default
- whether booking records should store full event snapshots or normalized foreign keys plus summary fields

## Recommendation

Start with Phase 1 and Phase 2 only after credentials are available, because the seed pipeline and resolver tooling depend on the real database setup.
