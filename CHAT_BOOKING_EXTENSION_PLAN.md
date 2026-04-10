# Conversational Booking Extension Plan

## Goal

Extend the current MVP so users can complete a booking through chat messages, not only by clicking the booking button on result cards.

## Product Behavior

### Search-first routing

Every incoming user message should first be checked for booking intent.

- if the message is not booking-related, continue through the existing filter-resolution and search flow
- if the message is booking-related, route it through a dedicated booking mini agent

### Booking flow

1. User searches normally and receives matched event cards.
2. The thread stores the exact result context that was shown to the user.
3. User says something like `book the second one`.
4. Booking mini agent reads the current thread result context and resolves the target event.
5. The resolved event is saved as a thread-scoped pending selection.
6. Assistant asks for confirmation and the selected event is highlighted in the UI.
7. User replies with `yes`, `confirm`, `go ahead`, or a negative reply.
8. If confirmed, the selected event is inserted into `bookings` using the same deterministic booking logic used by the button flow.
9. If rejected, the pending selection is cleared.

## Architecture

### New mini agent

Add one booking mini agent responsible only for:

- detecting whether a turn is booking-related
- resolving which event from the current thread result context the user means
- detecting confirmation responses
- detecting rejection or cancellation responses

The booking mini agent should not query the event catalog directly.

### Booking tools

Add three booking tools:

1. `get_current_thread_result_context(thread_id)`
   Returns the ordered result set last shown to the user in this thread.

2. `mark_thread_pending_booking(thread_id, listing_code)`
   Stores the selected event as pending confirmation for this thread.

3. `confirm_thread_pending_booking(thread_id)`
   Creates the booking from the pending thread selection and clears the pending state.

Optional follow-up tool:

4. `clear_thread_pending_booking(thread_id)`
   Clears the thread’s pending booking when the user rejects it.

## Persistence model

Do not mutate shared event rows to mark selection.

Store booking selection at the thread level instead.

### Suggested thread-scoped state

Persist this inside `thread_filters`:

- `latest_result_context`
  - the ordered list of results last shown in the chat
  - includes listing code and display snapshot fields
- `pending_booking`
  - selected listing code
  - selected event snapshot
  - status such as `pending_confirmation`
  - created_at or updated_at timestamp

This keeps all conversational state local to a thread and safe across users.

## Booking mini agent contract

### Input

- current thread id
- user message
- whether a pending booking already exists

### Output

Structured output should include:

- `intent`
  - `none`
  - `select_booking`
  - `confirm_booking`
  - `reject_booking`
  - `ambiguous`
- `status`
  - `resolved`
  - `ambiguous`
  - `no_match`
  - `no_input`
- `listing_code`
- `message`
- `candidates`

## Backend flow changes

## Step 1

Persist the latest displayed result context after every search turn.

Rules:

- save the exact ordered results shown to the user
- clear stale pending booking whenever a new search changes the result context
- if the turn produces no results, store an empty result context

## Step 2

Run the booking mini agent at the start of `process_chat_turn`.

Decision path:

- if booking intent is `none`, continue through normal filter flow
- if booking intent is `select_booking`, resolve the target, mark pending booking, and return a confirmation prompt
- if booking intent is `confirm_booking`, confirm the pending booking
- if booking intent is `reject_booking`, clear the pending selection and continue the conversation

## Step 3

Reuse deterministic booking persistence.

The final booking insert must still be deterministic and use the exact resolved `listing_code`.

## UI changes

### Chat response area

- when a pending booking exists, show the selected event card in a confirmation state
- disable normal booking buttons while the thread is waiting for confirmation if needed

### Thread detail payload

Expose:

- `latest_result_context`
- `pending_booking`

This allows the frontend to render pending state after refresh or thread switching.

## Validation rules

- booking resolution must only use the current thread result context
- never book an event that is not present in the saved thread result context
- if the user says `yes` without a pending selection, ask them to choose an event first
- if multiple results could match, ask for clarification
- if the thread is already booked, do not allow another booking in that thread

## First-turn utterances to support

### Selection

- `book the first one`
- `book the second match`
- `book the Mumbai one`
- `book Kalki`
- `book the Chennai movie`

### Confirmation

- `yes`
- `yes, this one`
- `confirm`
- `go ahead`

### Rejection

- `no`
- `not this one`
- `cancel`

## Verification plan

### Happy path

1. Search for sports events.
2. Say `book the second one`.
3. Confirm with `yes`.
4. Verify booking row is created and thread becomes booked.

### Movie path

1. Search for movies in a city.
2. Say `book the Kalki one`.
3. Confirm.
4. Verify booking row and assistant confirmation message.

### Ambiguous selection

1. Search results include multiple similar titles.
2. Say `book that one`.
3. Verify assistant asks which result was meant.

### No pending confirmation

1. Say `yes` without selecting an event first.
2. Verify the system asks the user to choose an event first.

### Rejection

1. Select a pending booking.
2. Say `no`.
3. Verify pending booking is cleared and no booking row is created.

### Result-context safety

1. Search and get results.
2. Change filters so the result list changes.
3. Verify old pending booking is cleared.

### Refresh persistence

1. Select a pending booking.
2. Refresh the page.
3. Verify the pending selected card still appears.
