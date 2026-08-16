<div align="center">

# Dineflow Backend

AI restaurant ordering agent — FastAPI + [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/)

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![OpenAI Agents SDK](https://img.shields.io/badge/OpenAI_Agents_SDK-GPT--5-412991?logo=openai&logoColor=white)](https://openai.github.io/openai-agents-python/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![MongoDB](https://img.shields.io/badge/MongoDB-47A248?logo=mongodb&logoColor=white)](https://www.mongodb.com/)
[![Deployed on FastAPI Cloud](https://img.shields.io/badge/FastAPI_Cloud-6D7FFF?logo=fastapi&logoColor=white)](https://dineflow-be-5bc08f20.fastapicloud.dev)

**Live API:** [https://dineflow-be-5bc08f20.fastapicloud.dev](https://dineflow-be-5bc08f20.fastapicloud.dev) · **Interactive docs:** [https://dineflow-be-5bc08f20.fastapicloud.dev/docs](https://dineflow-be-5bc08f20.fastapicloud.dev/docs)

</div>

---

## Overview

Dineflow is an AI-powered restaurant ordering assistant. Customers chat with a natural-language agent that can browse the menu, place orders, and track their status in real time — while a kitchen dashboard receives order events as they happen.

This repository is the **backend**: a FastAPI service that runs the agent (OpenAI Agents SDK + GPT-5) and streams its responses to the frontend over Server-Sent Events (SSE).

The companion frontend lives in the **[dineflow-fe](https://github.com/TalhaAbid420/dineflow-fe)** repository.

## Features

- **Conversational ordering agent** — powered by GPT-5 via the OpenAI Agents SDK, with tool use for menu browsing, ordering, and order-status checks.
- **SSE streaming chat** — `POST /api/chat` streams text deltas, tool calls, menu cards, and order events in real time.
- **Dual-memory architecture**
  - **PostgreSQL** — menu items, orders, short-term conversation history, and users.
  - **MongoDB** — long-term customer memories (preferences and personal details extracted from each conversation).
- **JWT authentication** — customer registration/login plus a seeded chef account for the kitchen dashboard.
- **Live order events** — SSE feed (`GET /api/events`) that notifies the kitchen the moment an order is placed.
- **Automatic seeding** — a sample 11-item menu and the chef account are created on first start.
- **Auto-generated menu images** — images are fetched and attached to menu items on startup when available.

## Tech Stack

| Layer      | Technology                                                        |
| ---------- | ----------------------------------------------------------------- |
| Language   | Python 3.11+                                                       |
| Framework  | [FastAPI](https://fastapi.tiangolo.com/) + Uvicorn                 |
| Agent      | [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/) (GPT-5) |
| Database   | PostgreSQL ([asyncpg](https://github.com/MagicStack/asyncpg))     |
| Memory     | MongoDB ([Motor](https://www.mongodb.com/docs/drivers/motor/))     |
| Config     | [Pydantic Settings](https://docs.pydantic.dev/latest/usage/pydantic_settings/) |
| Tooling    | [uv](https://docs.astral.sh/uv/), Docker Compose                  |

## Getting Started

### Prerequisites

- Python 3.11+ and [uv](https://docs.astral.sh/uv/) (or pip/venv)
- [Docker](https://www.docker.com/) for the local PostgreSQL + MongoDB (optional — use hosted DBs if you prefer)

### 1. Clone & install

```bash
git clone https://github.com/TalhaAbid420/dineflow-be.git
cd dineflow-be
uv sync
```

### 2. Configure environment

Copy `.env.example` to `.env` and fill in the values:

```bash
cp .env.example .env
```

At minimum set:

```dotenv
OPENAI_API_KEY=sk-...
POSTGRES_DATABASE_URL=postgresql://dineflow:dineflow@localhost:5432/dineflow
MONGODB_URI=mongodb://localhost:27017
```

See [`.env.example`](.env.example) for every option (LLM model, CORS origins, JWT secret, chef credentials, seeding, etc.).

### 3. Start local databases

```bash
docker compose up db mongo -d
```

### 4. Run the server

```bash
uv run uvicorn main:app --reload --port 8000
```

The API is now at [http://localhost:8000](http://localhost:8000), with interactive docs at [http://localhost:8000/docs](http://localhost:8000/docs).

## API Reference

| Method | Path                          | Auth   | Description                                        |
| ------ | ----------------------------- | ------ | -------------------------------------------------- |
| `GET`  | `/health`                     | —      | Liveness probe with runtime environment            |
| `POST` | `/api/auth/register`          | —      | Create a customer account                          |
| `POST` | `/api/auth/login`             | —      | Obtain a JWT token                                 |
| `GET`  | `/api/auth/me`                | Bearer | Current user profile                               |
| `POST` | `/api/chat`                   | Bearer | Stream the agent's reply over SSE                  |
| `GET`  | `/api/events`                 | Bearer | SSE feed of order events for the kitchen           |
| `GET`  | `/api/menu/{item_id}/image`   | —      | Serve a menu item's image                          |
| `GET`  | `/api/orders`                 | Bearer | All orders (chef)                                  |
| `GET`  | `/api/orders/mine`            | Bearer | Current user's orders                              |
| `PATCH`| `/api/orders/{order_id}/status` | Bearer | Update an order's status (chef)                  |

### Chat SSE events

`POST /api/chat` streams `data:` JSON frames of type:

| Event             | Payload                                    | Meaning                             |
| ----------------- | ------------------------------------------ | ----------------------------------- |
| `delta`           | `{ content }`                              | Streaming text token                |
| `tool`            | `{ name, arguments }`                      | Agent invoked a tool                |
| `menu`            | `{ items }`                                | Menu items rendered as cards        |
| `menu_categories` | `{ categories }`                           | Available categories (chips)        |
| `order`           | `{ order }`                                | An order was placed                 |
| `done`            | `{ content }`                              | Final assistant text                |
| `error`           | `{ message }`                              | Agent run failed                    |

## Agent Tools

The agent has access to:

- `get_menu` — list categories or the items within one category.
- `place_order` — place an order for the current user.
- `check_order_status` — look up the status of a previous order.

## Project Structure

```
dineflow-be/
├── main.py                 # FastAPI app, lifespan (DB init, seeding), CORS
├── pyproject.toml          # Dependencies (uv)
├── docker-compose.yml      # Local PostgreSQL + MongoDB
├── Dockerfile              # Container image
└── app/
    ├── config.py           # Pydantic settings (env / .env)
    ├── security.py         # Password hashing + JWT helpers
    ├── deps.py             # FastAPI dependencies (auth)
    ├── pubsub.py           # In-process order event bus (SSE fan-out)
    ├── agent/
    │   ├── agent.py        # Builds the OpenAI agent with tools
    │   ├── memory.py       # Short-term history + long-term preferences
    │   └── prompts.py      # System prompts / instructions
    ├── routers/
    │   ├── auth.py         # Register / login / me
    │   ├── chat.py         # SSE chat streaming
    │   ├── events.py       # SSE order events
    │   ├── menu.py         # Menu image serving
    │   └── orders.py       # Order listing + status updates
    ├── db/
    │   ├── postgres.py     # Pool, schema init, queries
    │   ├── mongodb.py      # Long-term memory collection
    │   ├── seed.py         # Sample menu + chef account
    │   └── images.py       # Menu item image import
    └── tools/
        ├── menu.py         # get_menu tool
        ├── ordering.py     # place_order tool
        └── status.py       # check_order_status tool
```

## Deployment

The API is deployed on **FastAPI Cloud**. Deploys are pushed from this repository:

```bash
fastapi cloud deploy
```

Environment variables (API keys, database URLs, JWT secret) are managed in the FastAPI Cloud dashboard or with:

```bash
fastapi cloud env set KEY VALUE [--secret]
```

For a Vercel-hosted frontend, point `BACKEND_URL` at this service.

## Related

- [dineflow-fe](https://github.com/TalhaAbid420/dineflow-fe) — Next.js chat frontend + kitchen dashboard
- Live app: [https://dineflow-fe-eight.vercel.app](https://dineflow-fe-eight.vercel.app)

## License

Private — all rights reserved.
