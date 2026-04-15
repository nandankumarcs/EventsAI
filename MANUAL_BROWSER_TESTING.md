# Manual Browser Testing — Chat Search + Booking (Attend MVP)

## Goal

Manually verify the chat-driven event discovery + booking flow in the browser matches the API regression expectations.

This guide is intentionally written as **click-by-click + what to verify**, so you can run it without reading backend logs.

---

## Prerequisites

- Backend running:
  - `http://127.0.0.1:8000`
- Frontend running:
  - Open `http://127.0.0.1:4173`
- DB seeded with future-only sports + movies.

---

## What to watch in the UI

For each step below, verify (as applicable):

- **Thread created / reused**
  - New message appears in the same thread.
  - The thread title is reasonable.
- **Filters + results**
  - Results shown match the user request.
  - When you correct/remove filters, results update accordingly.
  - Domain switch (movies → sports) should not leak movie-only filters.
- **Booking state**
  - When an event is selected, you should see a clear selection/pending state.
  - Confirmation and user-info capture proceeds field-by-field.
  - Thread should become booked only when the booking is actually confirmed.

---

## Section M — Full Positive Manual Regression (Sequences 1–7)

### Sequence 1 — Sports discovery + follow-ups (same thread)

1. **Message**: `Show me upcoming football matches`
   - **Expect**:
     - Sports results appear.
     - Football intent is reflected in the results.

2. **Message**: `show me more`
   - **Expect**:
     - Results remain sports.
     - The assistant either paginates or clearly explains how to browse more.

3. **Message**: `Remove the city filter`
   - **Expect**:
     - If a city was inferred earlier, it should be removed.
     - Football results should still be shown.
     - No unrelated filters appear.

4. **Message**: `No date restriction`
   - **Expect**:
     - Date constraints removed.
     - Results still shown; no filter overreach.

---

### Sequence 2 — Sports accumulation (fresh thread)

Start a **new thread**.

1. **Message**: `Sports`
   - **Expect**: sports discovery response.

2. **Message**: `in Mumbai`
   - **Expect**: results narrow to Mumbai.

3. **Message**: `this Sunday`
   - **Expect**: date filter applied; results update.

4. **Message**: `around 7pm`
   - **Expect**: time window applied; results update.

5. **Message**: `cricket`
   - **Expect**: sport type becomes cricket; results update.

---

### Sequence 3 — City correction (fresh thread)

Start a **new thread**.

1. **Message**: `Show cricket in Delhi`
   - **Expect**: sports + cricket in Delhi (canonicalized to New Delhi if applicable).

2. **Message**: `Actually Mumbai again`
   - **Expect**: city changes to Mumbai, not both cities.

---

### Sequence 4 — Movies discovery (fresh thread)

Start a **new thread**.

1. **Message**: `Show Hindi movies in Mumbai`
   - **Expect**:
     - Movie results appear.
     - City is Mumbai.
     - Language is Hindi.

---

### Sequence 5 — Domain switch (same thread as Sequence 4)

Continue in the **same thread** from Sequence 4.

1. **Message**: `Show cricket matches`
   - **Expect**:
     - Domain switches to sports.
     - Sport type becomes cricket.
     - Movie-specific constraints should not persist.

---

### Sequence 6 — Booking happy path (fresh thread)

Start a **new thread**.

1. **Message**: `Show cricket matches in Mumbai`
   - **Expect**: multiple results displayed.

2. **Message**: `book the second one`
   - **Expect**:
     - The second visible result is selected.
     - UI indicates selection/pending booking.

3. **Message**: `yes`
   - **Expect**:
     - Booking does not finalize immediately if info is missing.
     - Assistant asks for the next missing field (usually name).

4. **Message**: `Nandan Kumar`
   - **Expect**: asks for email next.

5. **Message**: `nandan@example.com`
   - **Expect**: asks for contact number next.

6. **Message**: `9999999999`
   - **Expect**:
     - Booking confirmation message with booking reference.
     - Thread becomes booked at this point.
     - No error toast or “thread already booked” interruption during this same turn.

---

### Sequence 7 — Booking flexibility (fresh thread)

Start a **new thread**.

1. **Message**: `Show cricket matches`
   - **Expect**: results displayed.

2. **Message**: `book the second one`
   - **Expect**: selection pending.

3. **Message**: `yes`
   - **Expect**: asks for user info (awaiting info) rather than forcing completion.

4. **Message**: `book the other one instead`
   - **Expect**:
     - Booking selection is cleared.
     - Existing results are shown again (so you can choose again).

5. **Message**: `Actually book the Delhi one instead`
   - **Expect** (Spec A):
     - This is treated as a **search change**.
     - City should update to New Delhi and results should update.
     - No automatic booking selection.

6. **Message**: `Show football matches instead`
   - **Expect**:
     - Sport type switches to football.
     - Results update accordingly.

---

## Quick Manual Checks (high-value negatives)

These come from `NEGATIVE_TESTING_PLAN.md` and are useful for browser-only verification.

### Domain support / hallucination guard

1. **Message**: `Show concerts in Mumbai`
   - **Expect**: clear “unsupported domain” style response; no invented events.

### Unsupported constraints

1. **Message**: `Movies in IMAX 5D`
   - **Expect**: no fabrication; either no-match or a clarification.

### XSS rendering safety

1. **Message**: `<script>alert('xss')</script>`
   - **Expect**: displayed as literal text (no script execution).

### Empty input guard

1. Send an empty message / whitespace.
   - **Expect**: send disabled or UI rejects it without breaking.

---

## Troubleshooting

- If responses appear delayed:
  - Wait for completion; avoid sending multiple messages rapidly.
- If a thread becomes booked:
  - Verify the UI blocks further booking in that thread and suggests starting a new thread.
- If results disappear unexpectedly:
  - Re-send the last “search” message (e.g., `Show cricket matches in Mumbai`) and confirm results rehydrate.
