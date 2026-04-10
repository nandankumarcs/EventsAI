# Negative Feature Testing Plan — Attend MVP (Chat UI)

## Goal

Test every negative and edge-case **user scenario through the chatbox** to verify the assistant handles bad inputs, impossible requests, ambiguous queries, and workflow violations gracefully — with clear, helpful responses and no dead-end states.

---

## Test Labels

- `Must-pass`: Required for MVP signoff. A failure here is a real blocker.
- `Exploratory`: Valuable stress or product-shaping scenario. A failure here may indicate a limitation rather than a release blocker.

---

## How Testing Will Work

1. Open the frontend at `http://127.0.0.1:4173`
2. Use the chatbox to send messages for each scenario
3. Verify the assistant response is **helpful, accurate, and non-broken**
4. Verify the UI renders correctly (no layout breakage, no stale state)
5. Record browser sessions for key flows

---

## Test Categories

### Category A — Nonsensical & Irrelevant Input

| # | Label | Chat Message | Expected Behavior |
|---|-------|-------------|-------------------|
| A1 | Must-pass | `asdfghjkl` | Assistant responds gracefully and stays product-scoped |
| A2 | Must-pass | `hello` | Friendly greeting or prompt to discover events |
| A3 | Exploratory | `what is the meaning of life?` | Should stay on event discovery and avoid acting like a general-purpose assistant |
| A4 | Exploratory | `tell me a joke` | Should stay on-topic or gently redirect |
| A5 | Must-pass | `         ` (spaces only) | Send button should be disabled or message rejected |
| A6 | Must-pass | `🎬🍿🏏⚽` (emoji only) | Graceful response, not a crash |
| A7 | Must-pass | `<script>alert('xss')</script>` | Renders as plain text, no script execution |
| A8 | Exploratory | Very long message (2000+ chars of random text) | Should process without breaking layout or hanging the UI |

---

### Category B — Events That Don't Exist

| # | Label | Chat Message | Expected Behavior |
|---|-------|-------------|-------------------|
| B1 | Must-pass | `Show me handball events in Mumbai` | "No matching" response — does NOT show unrelated sports |
| B2 | Must-pass | `Movies in Atlantis` | No results, suggests trying a different city |
| B3 | Must-pass | `Cricket matches in Paris` | No results, helpful suggestion |
| B4 | Must-pass | `Show me F1 races` | No match for sport type, asks to try available sports |
| B5 | Must-pass | `Movies directed by Steven Spielberg` | If not in DB, should say no match — not invent results |
| B6 | Must-pass | `Movies in IMAX 5D` | No match for format, doesn't show other formats |
| B7 | Must-pass | `Sports on December 25, 2030` | No events that far out, says no results |
| B8 | Must-pass | `Show me concerts` | Event type not supported (only movies/sports), clear messaging |

---

### Category C — Contradictory & Conflicting Filters

| # | Label | Chat Sequence | Expected Behavior |
|---|-------|--------------|-------------------|
| C1 | Must-pass | `Show movies` → `Show cricket matches` | Switches domain to sports, clears movie-specific filters |
| C2 | Must-pass | `Sports in Mumbai` → `Actually Delhi` → `No wait, Pune` → `Actually Mumbai again` | Each correction replaces city cleanly, no stale city filters |
| C3 | Must-pass | `Movies this Sunday` → `No, next weekend` → `Actually today` | Date filter replaces cleanly each time |
| C4 | Exploratory | `Sports in Mumbai and Delhi at the same time` | Should either support multi-city coherently or ask for clarification |
| C5 | Exploratory | `Movies before 6am and after 11pm` | Should handle impossible time window gracefully |
| C6 | Must-pass | `Show cricket` → `Show me that but in IMAX` | IMAX is not applicable to sports — agent should clarify or reject cleanly |
| C7 | Exploratory | `Movies in Hindi` → `Show sports instead` → `Show movies again` | Domain round-trip should remain coherent; note any stale filter leakage |

---

### Category D — Booked Thread Violations

| # | Label | Action | Expected Behavior |
|---|-------|--------|-------------------|
| D1 | Must-pass | Book an event → try sending another message in same thread | Chat input disabled/blocked, read-only guidance shown |
| D2 | Must-pass | Book an event → refresh page → verify thread is still booked | Thread remains booked, confirmation message persists |
| D3 | Must-pass | Book an event → try clicking "Book" on a different result card or trigger booking API with another listing | Should be rejected — thread already has a booking |
| D4 | Must-pass | After booking, verify "New Thread" CTA works | New thread starts clean with no leftover filters |

---

### Category E — Empty & Zero-Result Scenarios

| # | Label | Chat Message | Expected Behavior |
|---|-------|-------------|-------------------|
| E1 | Must-pass | `Show me movies` with very narrow filters that yield 0 results | "No results found" + suggestion to broaden filters |
| E2 | Must-pass | `Cricket in Mumbai this Sunday at 3am` | Likely zero results for 3am cricket — helpful message |
| E3 | Must-pass | After getting results → add impossible filter → zero results | Clear messaging about no match with current filters |
| E4 | Exploratory | Start with an extremely specific query: `UA certified Hindi comedy movies directed by Amar Kaushik in IMAX at PVR Phoenix Mumbai this Sunday at 7pm` | Either finds match or gives clear "too narrow" feedback |

---

### Category F — Rapid & Abusive Interaction Patterns

| # | Label | Action | Expected Behavior |
|---|-------|--------|-------------------|
| F1 | Must-pass | Send 5 messages rapidly without waiting for response | No duplicate crashes or corrupted thread state; record whether excess sends are ignored, serialized, or blocked |
| F2 | Must-pass | Switch threads while a message is being processed | Current send completes or errors cleanly, no data corruption or cross-thread leakage |
| F3 | Must-pass | Create multiple new threads rapidly | Each thread created correctly, sidebar updates |
| F4 | Exploratory | Click Book while agent is still responding | Booking only triggers on explicit user action, no race |

---

### Category G — Ambiguous & Vague Queries

| # | Label | Chat Message | Expected Behavior |
|---|-------|-------------|-------------------|
| G1 | Must-pass | `Show me something fun` | Should ask what type of event (movies/sports) or show both coherently |
| G2 | Must-pass | `Sports in Delhi` (if Delhi maps to multiple options) | Asks for clarification or resolves to canonical "New Delhi" |
| G3 | Must-pass | `I want to watch something` | Asks for more context — movies or sports? |
| G4 | Must-pass | `Cheap tickets` | Asks for clarification on event type, location, etc. |
| G5 | Exploratory | `Something for kids this weekend` | Should ask for details or apply a safe interpretation without inventing unsupported metadata |
| G6 | Must-pass | `What do you have?` | Should present available categories or ask for preference |

---

### Category H — Filter Removal & Reset

| # | Label | Chat Sequence | Expected Behavior |
|---|-------|--------------|-------------------|
| H1 | Must-pass | `Cricket in Mumbai` → `Remove the Mumbai filter` | City filter cleared, shows cricket across all cities |
| H2 | Exploratory | `Movies in Delhi on Sunday at 7pm` → `Show me all dates instead` | Date/time filters cleared, rest preserved |
| H3 | Exploratory | `Sports` → add 3-4 filters → `Start over` or `Clear all filters` | All filters reset, fresh search |
| H4 | Exploratory | `Cricket in Mumbai` → `Show me matches outside Mumbai` | Should clear Mumbai and possibly search other cities |

---

### Category I — Multi-Turn Context Coherence

| # | Label | Chat Sequence | Expected Behavior |
|---|-------|--------------|-------------------|
| I1 | Must-pass | `Sports` → `in Mumbai` → `this sunday` → `around 7pm` → `cricket` → verify all 5 filters accumulated correctly | Thread filters panel shows all 5 filters active |
| I2 | Must-pass | Long conversation (10+ turns) → verify filter state hasn't drifted | Filters only contain what user explicitly set/changed |
| I3 | Must-pass | `Movies in Mumbai` → 5 irrelevant messages like `thanks`, `cool`, `nice` → `Show me more` | Filters should persist through non-filter messages |
| I4 | Exploratory | `Show cricket` → `Who is playing?` | Agent should answer from current grounded context or respond safely without losing state |

---

### Category J — Retry, Transport & Backend Failure

| # | Label | Action | Expected Behavior |
|---|-------|--------|-------------------|
| J1 | Must-pass | Draft a message → bring backend down → send | Action error banner shown, retry action available, no UI dead end |
| J2 | Must-pass | After J1, bring backend back → click `Retry sending message` | Message is sent once, thread updates correctly, no duplicate assistant turn |
| J3 | Must-pass | Fail a send → switch threads before retry | Retry does not corrupt or append into the wrong thread |
| J4 | Exploratory | Fail a send → refresh page | App recovers cleanly; document whether retry survives refresh or requires resubmission |

---

### Category K — API Rejection & Workflow Guardrails

These are not pure chatbox interactions, but they are essential companions to browser negative testing because the chat UI depends on these protections.

| # | Label | Action | Expected Behavior |
|---|-------|--------|-------------------|
| K1 | Must-pass | `POST /api/agents/chat/` with missing `message` | `400` with stable error payload, no server crash |
| K2 | Must-pass | `POST /api/agents/chat/` with invalid JSON | `400` with stable error payload, no server crash |
| K3 | Must-pass | `POST /api/agents/chat/` against a booked thread | `409` and no new message appended |
| K4 | Must-pass | `POST /api/agents/chat/` against an archived thread | `409` and no new message appended |
| K5 | Must-pass | `POST /api/bookings/confirm/` with missing inputs | `400` with stable error payload |
| K6 | Must-pass | `POST /api/bookings/confirm/` with invalid `listing_code` | `404` with stable error payload |
| K7 | Must-pass | Simulate resolver/model failure during chat turn | Request should fail gracefully without a server 500 or corrupted thread state |

---

## Suggested Execution Order

| Priority | Category | Rationale |
|----------|----------|-----------|
| 1 | **B** (Non-existent events) | Core negative path — must never show fake results |
| 2 | **D** (Booked thread violations) | Critical workflow integrity |
| 3 | **J** (Retry / backend failure) | Most important failure-and-recovery path in the composer |
| 4 | **C** (Contradictory filters) | Filter state correctness under pressure |
| 5 | **E** (Zero-result scenarios) | User experience on dead ends |
| 6 | **K** (API rejection / guardrails) | Verifies backend refuses invalid or forbidden mutations |
| 7 | **H** (Filter removal) | Filter management edge cases |
| 8 | **G** (Ambiguous queries) | Conversational intelligence quality |
| 9 | **I** (Multi-turn coherence) | State persistence over long conversations |
| 10 | **A** (Nonsensical input) | Robustness against garbage input |
| 11 | **F** (Rapid interactions) | UI resilience under abuse |

---

## Exit Criteria

- [ ] Assistant **never shows fabricated/hallucinated events** — all results come from the deterministic query layer
- [ ] Every zero-result scenario has a **clear, helpful next-step suggestion**
- [ ] Booked threads are **fully locked** — no way to send messages or create new bookings
- [ ] Retry and backend-recovery flows work without duplicate turns or cross-thread corruption
- [ ] Filter state remains **consistent and correct** through contradictions, corrections, and domain switches
- [ ] UI **never enters a dead-end state** — there's always a path forward (new thread, retry, etc.)
- [ ] No **layout breakage** from long messages, special characters, or emoji
- [ ] No **XSS or injection** succeeds through the chatbox
- [ ] Agent stays **on-topic** and doesn't become a general-purpose chatbot
- [ ] Backend rejects invalid, booked, and archived chat mutations with stable non-500 responses
