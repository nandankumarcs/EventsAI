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
- backend: Flask, SQLAlchemy, Alembic, PostgreSQL, LangChain, OpenAI API
- data: seeded `movie_events` and `sport_events` tables with future-only records
- process manager: PM2 (production)

## Repository Layout

```text
.
├── backend
│   ├── apps
│   │   ├── agents
│   │   ├── bookings
│   │   ├── chats
│   │   ├── core
│   │   ├── events
│   │   └── flights
│   ├── flask_app                  # Flask app factory, blueprints, ORM models
│   ├── flask_wsgi.py              # WSGI entry point
│   ├── start.py                   # Startup script (reads PORT from env)
│   └── requirements.txt
├── frontend
│   ├── src
│   │   ├── components
│   │   └── lib
│   └── package.json
├── ecosystem.config.cjs           # PM2 process manager config
└── README.md
```

## Environment Setup

### Backend

Copy `backend/.env.example` to `backend/.env` and configure:

```bash
SECRET_KEY=replace-me
DEBUG=true
DATABASE_URL=postgres://username:password@host:port/database?sslmode=require
OPENAI_API_KEY=replace-me
OPENAI_CHAT_MODEL=gpt-4.1-mini
OPENAI_RESOLVER_MODEL=gpt-4.1-mini
PORT=8000
```

### Frontend

Copy `frontend/.env.example` to `frontend/.env`:

```bash
VITE_API_BASE_URL=http://127.0.0.1:8000
```

## Local Run

### One-time setup (fresh clone)

```bash
# 1. Create virtualenv and install dependencies
python3 -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements.txt

# 2. Copy environment file and configure
cp backend/.env.example backend/.env
# Edit backend/.env with your DATABASE_URL, OPENAI_API_KEY, etc.

# 3. Install frontend dependencies and build
cd frontend && npm install && npm run build && cd ..
```

### Seed data

The seed command resets and repopulates movie and sport catalog data with future-only events:

```bash
cd backend
.venv/bin/python -m scripts.seed_event_data --reset
```

### Start with PM2 (production)

```bash
pm2 start ecosystem.config.cjs
```

The app will:
- Read `PORT` from `backend/.env` (default: 8000)
- Serve API at `/api/*` and React SPA at root
- Run at **http://127.0.0.1:8000** (or whatever PORT is set)

### Start manually (development)

```bash
cd backend
.venv/bin/python start.py
```

### PM2 commands

```bash
pm2 status              # Check app status
pm2 logs attend-api     # View logs
pm2 stop attend-api     # Stop app
pm2 restart attend-api  # Restart app
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
# Run health check
curl http://127.0.0.1:8000/api/health/

# Run chat edge case verification
python3 verify_chat_edge_cases.py
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
