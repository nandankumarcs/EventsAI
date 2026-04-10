# Events AI

EventsAI is a chat-first event discovery and booking platform inspired by the filter flow of booking platforms like BookMyShow. Instead of clicking filters, users describe what they want in natural language and the system builds a persisted filter state per thread.

The current MVP supports:

- movie and sport discovery through chat
- persisted chat threads, messages, and filter state
- DB-backed filter resolution with LangChain mini agents
- deterministic event search against PostgreSQL
- simulated booking confirmation stored in the database

## Stack

- frontend: React, TypeScript, Vite, Tailwind, shadcn components
- backend: Django, PostgreSQL, LangChain, OpenAI API
- data: seeded `movie_events` and `sport_events` tables with future-only records

## Repository Layout

```text
.
├── backend
│   ├── apps
│   │   ├── agents
│   │   ├── bookings
│   │   ├── chats
│   │   ├── core
│   │   └── events
│   ├── config
│   ├── manage.py
│   └── requirements.txt
├── frontend
│   ├── src
│   │   ├── components
│   │   └── lib
│   └── package.json
├── start.sh                       # unified build + run script
├── Makefile                       # convenience wrapper for start.sh
└── PHASEWISE_IMPLEMENTATION_PLAN.md
```

## Environment Setup

### Backend

Copy `backend/.env.example` to `backend/.env` and configure:

```bash
DJANGO_SECRET_KEY=replace-me
DJANGO_DEBUG=true
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost
DJANGO_CORS_ALLOWED_ORIGINS=http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:5174,http://localhost:5174
DATABASE_URL=postgres://username:password@host:port/database?sslmode=require
OPENAI_API_KEY=replace-me
OPENAI_CHAT_MODEL=gpt-4.1-mini
OPENAI_RESOLVER_MODEL=gpt-4.1-mini
```

### Frontend

Copy `frontend/.env.example` to `frontend/.env`:

```bash
VITE_API_BASE_URL=http://127.0.0.1:8000
```

## Local Run

### One-time setup

```bash
# Backend — create venv and install Python deps
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
cd ..

# Frontend — install Node deps
cd frontend && npm install && cd ..
```

### Seed data

The seed command resets and repopulates movie and sport catalog data with future-only events:

```bash
cd backend
.venv/bin/python manage.py seed_event_data --reset
```

### Start (unified command)

From the **project root**, run either of the following — they are equivalent:

```bash
./start.sh
# or
make start
```

This will:
1. Build the React frontend (`npm run build` → `frontend/dist/`)
2. Start the Django server at **http://127.0.0.1:8000**

The server now serves both the API (`/api/*`) and the compiled React SPA from a single origin. No separate frontend dev server is needed.

Open [http://127.0.0.1:8000](http://127.0.0.1:8000).

### Running backend only (no frontend rebuild)

```bash
make runserver
# or
cd backend && .venv/bin/python manage.py runserver
```

## Core API Endpoints

- `GET /api/health/`
- `GET /api/chats/threads/`
- `POST /api/chats/threads/`
- `GET /api/chats/threads/<thread_id>/`
- `POST /api/agents/chat/`
- `GET /api/bookings/`
- `POST /api/bookings/confirm/`

## How The MVP Works

1. A user sends a message in a thread.
2. The main chat flow calls DB-backed resolver tools through mini agents to normalize categorical filters.
3. Temporal phrases are normalized deterministically.
4. The resolved filter state is merged into the thread's saved `thread_filters` row.
5. Deterministic search functions query `movie_events` or `sport_events`.
6. The assistant responds using grounded results, not freeform invented listings.
7. A booking confirmation writes to `bookings` and closes the thread into a read-only booked state.

## Verification Commands

### Backend

```bash
cd backend
.venv/bin/python manage.py check
.venv/bin/python manage.py test apps.chats apps.bookings apps.agents apps.events --keepdb
```

### Frontend

```bash
cd frontend
npm run lint
npm run build
```

## Known MVP Limitations

- no showtimes selection flow beyond the seeded event listing start time
- no seat map, payment flow, cancellation flow, or auth
- no right-side applied-filters panel yet
- no bookings page in the frontend yet, although bookings are persisted in the database
- thread ownership and multi-user support are not implemented
- LangGraph is intentionally not used yet

## Notes For The Next Iteration

- add a bookings page backed by `GET /api/bookings/`
- expose the current filter state in a dedicated right rail
- improve clarification behavior when the user expresses preference changes in more complex ways
- consider stronger structured traces for mini-agent reasoning in the thread metadata
