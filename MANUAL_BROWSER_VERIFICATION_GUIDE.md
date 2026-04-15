# Manual Browser Verification Guide

## Purpose

Use this guide to manually verify the app in the browser and report back any bugs, gaps, regressions, or UX issues.

This guide covers:

- core happy-path search and booking flows
- follow-up edits and corrections
- distraction handling and soft redirection
- booking flexibility
- negative and guardrail cases

Primary app URL:

- `http://127.0.0.1:8000`

Related reference docs:

- [`/Users/mac/Documents/attend-poc/FULL_VERIFICATION_PLAN.md`](/Users/mac/Documents/attend-poc/FULL_VERIFICATION_PLAN.md)
- [`/Users/mac/Documents/attend-poc/NEGATIVE_TESTING_PLAN.md`](/Users/mac/Documents/attend-poc/NEGATIVE_TESTING_PLAN.md)
- [`/Users/mac/Documents/attend-poc/API_VERIFICATION_PLAN.md`](/Users/mac/Documents/attend-poc/API_VERIFICATION_PLAN.md)
- [`/Users/mac/Documents/attend-poc/API_VERIFICATION_RESULTS.md`](/Users/mac/Documents/attend-poc/API_VERIFICATION_RESULTS.md)

## Before You Start

Make sure:

- the backend is running
- the frontend loads successfully
- seeded future event data is available
- you can open the app and create a new thread

Recommended browser setup:

- use desktop width first
- keep DevTools open on `Network` and `Console` if convenient
- if possible, test in a fresh window or incognito session

## How To Record Findings

For each issue, please capture:

- the exact prompt(s) you sent
- what you expected
- what actually happened
- whether results were shown or hidden
- whether the thread title changed oddly
- whether the booking state looked wrong
- screenshot if the issue is visible

Use this format when reporting back:

```md
### Finding

- Case:
- Thread title:
- Prompt sequence:
- Expected:
- Actual:
- Severity: Low / Medium / High
- Screenshot:
- Notes:
```

## Positive Cases

These should work cleanly.

### P1. New Search Thread

1. Open the app.
2. Start a fresh thread.
3. Send: `Show me upcoming football matches`

Expected:

- a thread is created
- football or sports filters are inferred
- results are shown
- if location is unclear, results should still appear if usable filters were extracted
- the thread title should reflect the search goal, not generic text

Watch for:

- no results despite valid filters
- clarification without results
- strange thread title

### P2. Direct Movie Search

1. Start a fresh thread.
2. Send: `Show Hindi movies in Mumbai`

Expected:

- movie results in Mumbai are shown
- the thread stays in the movie domain
- reply is grounded in visible results

### P3. Direct Sports Search

1. Start a fresh thread.
2. Send: `Show cricket in Delhi`

Expected:

- sports results are shown
- city resolves cleanly to the supported canonical city if needed
- title reflects cricket in Delhi or New Delhi

### P4. Single-Result Booking Flow

1. Find a search that narrows to one visible result.
2. Send: `book this one`
3. If prompted, continue with:
   - `yes`
   - your name
   - your email
   - your phone number

Expected:

- no fake ambiguity when only one result is visible
- booking progresses cleanly
- final confirmation message names the selected event
- thread becomes booked

### P5. Multi-Result Booking By Reference

1. Run a search with multiple visible results.
2. Send: `book the second one`

Expected:

- the second visible result is selected
- confirmation or user-info flow begins
- it should not select a random item

## Search Follow-Up Cases

These are especially important because we recently hardened them.

### S1. City Correction

1. Start a fresh thread.
2. Send: `Show cricket in Delhi`
3. Then send: `Actually Mumbai again`

Expected:

- the city should change to Mumbai
- the domain should remain sports
- cricket results for Mumbai should appear
- the thread should not widen to unrelated domains
- the assistant should not talk as if you were trying to book something

Report if:

- city does not change
- event type changes unexpectedly
- movies appear in a sports-only correction
- the assistant says things like “choose from the listed New Delhi matches”

### S2. Another City Correction

1. Start a fresh thread.
2. Send: `Show cricket in Delhi`
3. Then send: `No wait Pune`

Expected:

- if Pune is supported, results should switch there
- if Pune is unsupported, the assistant should clearly say that and keep the rest of the search coherent
- it should still feel like a search correction, not a booking error

### S3. Domain Switch

1. Start a fresh thread.
2. Send: `Show movies`
3. Then send: `Show cricket matches`

Expected:

- thread should switch from movies to sports
- sports results should be shown
- it should not say cricket is invalid because the current domain is movies

### S4. Filter Replacement

1. Start a fresh thread.
2. Send: `Show football in Mumbai this week`
3. Then send one of:
   - `Actually Bengaluru`
   - `This weekend instead`
   - `Show cricket instead`

Expected:

- only the intended filter changes
- unrelated filters stay stable unless they truly conflict
- results update accordingly

### S5. Filter Removal

1. Start a fresh thread.
2. Send: `Show football in Mumbai this week`
3. Then send one of:
   - `Remove the city filter`
   - `Not Mumbai`
   - `No date restriction`

Expected:

- the removed filter is cleared
- the remaining search still works
- the assistant does not collapse into confusion or no-op

## Distraction And Redirection Cases

These help verify whether the assistant stays useful without being rigid.

### D1. Off-Track Prompt During Search

1. Start a fresh thread.
2. Send: `Show me upcoming football matches`
3. Then send: `Write a poem`

Expected:

- the assistant gives a brief soft redirect
- if grounded search context already exists, results should still remain visible
- title should remain about football matches, not poems

Bad signs:

- full poem answer
- results disappear for no reason
- title changes to the off-topic prompt

### D2. Small Talk During Search

1. Start a search thread with visible results.
2. Send: `haha nice`

Expected:

- short acknowledgment is okay
- assistant should keep the user on track
- results should remain visible if the search state is still grounded

### D3. Off-Track Prompt During Booking

1. Select an event and enter booking flow.
2. When asked for confirmation or user info, send: `Tell me a joke`

Expected:

- short redirect
- selected event should remain active
- booking context should not be lost
- results should still be visible if previously shown

### D4. Return To Task After Distraction

1. Run any of the distraction cases above.
2. Then reply with the actual next step, like:
   - `Okay show Mumbai matches`
   - `yes`
   - your name or email

Expected:

- the assistant should recover smoothly
- it should not forget the active goal

## Booking Flexibility Cases

These are very important.

### B1. Change Selection After Event Selection

1. Run a search with multiple visible results.
2. Select one result with `book this one` or `book the second one`
3. Before confirmation, send: `book the Mumbai one instead`

Expected:

- selected event changes
- booking flow continues with the new event
- assistant should not force you to cancel first

### B2. Change Selection During User Info Collection

1. Start booking an event.
2. Provide one or two user details.
3. Then send: `Actually book the Delhi one instead`

Expected:

- selected event changes
- already captured valid user info should be preserved if possible
- assistant should continue asking for whatever field is still missing

### B3. Search Change During Booking

1. Start booking an event.
2. While in confirmation or user-info stage, send: `Show football matches instead`

Expected:

- booking should not silently corrupt state
- app should transition back into search mode cleanly
- new results should be shown if the request is valid

## Negative Cases

These should fail safely.

### N1. Empty Input

1. Click send with an empty composer.
2. Try whitespace-only input if possible.

Expected:

- no meaningful request should be sent
- UI should not get stuck

### N2. Unsupported Request

1. Start a fresh thread.
2. Send: `Write a poem about the moon`

Expected:

- assistant should not fully comply as a general-purpose writer
- should redirect toward event discovery
- should not fabricate events

### N3. Unsupported Domain

1. Start a fresh thread.
2. Send: `Show concerts in Mumbai`

Expected:

- assistant should clearly stay within supported domains
- it should not invent concert results

### N4. Impossible Search

1. Start a fresh thread.
2. Send something highly restrictive like:
   - `Show handball in Mumbai at 3am this Sunday`

Expected:

- no fabricated results
- clear no-match response
- thread should remain usable afterward

### N5. Script Injection Text

1. Start a fresh thread.
2. Send: `<script>alert('xss')</script>`

Expected:

- the text should render as text
- no alert or script execution

### N6. Booked Thread Guard

1. Complete a booking so the thread becomes booked.
2. Try sending another search or booking request in the same thread.

Expected:

- thread should behave as read-only or reject further mutation
- no extra search or booking state should be appended

## Retry And Recovery Cases

If you want to go deeper, these are very useful.

### R1. Backend Outage During Send

1. Open the app with DevTools visible.
2. Stop the backend.
3. Try sending a message.
4. Restart the backend.
5. Use the app’s retry path if shown.

Expected:

- clear failure state
- retry path works after backend recovery
- no duplicate turns

### R2. Reload Persistence

1. Build a thread with filters and visible results.
2. Reload the page.

Expected:

- messages should persist
- active filters should persist
- visible results context should persist

## UI Things To Notice

Please note any of these if they happen:

- thread title changes to something random or off-topic
- results disappear when they should stay visible
- results stay visible when they clearly should not
- assistant starts answering off-topic requests too fully
- booking feels locked when it should remain flexible
- booking loses previously entered user info after reselection
- current goal feels forgotten after a distraction

## Recommended Manual Pass Order

If you want a focused pass, do this order:

1. `P1`
2. `S1`
3. `S3`
4. `D1`
5. `B1`
6. `B2`
7. `N3`
8. `N4`
9. `N6`
10. `R2`

## What To Send Back

When you’re done, the most useful feedback is:

- which cases passed cleanly
- which cases failed
- which ones felt awkward even if technically “correct”
- screenshots for visual or messaging issues
- exact prompt sequences for anything surprising

If you send me those findings, I’ll translate them into concrete bugs, root-cause them, and keep fixing the gaps.  
