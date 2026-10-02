# Flowmint AI

> Turn every signal into a revenue action.

Flowmint AI is a **bounded-autonomy revenue operating system** for AI-ready merchants. It combines commerce infrastructure, revenue intelligence, and controlled AI agents into a single platform.

## Architecture

- **Frontend**: React + Vite + TypeScript + Tailwind CSS
- **Backend**: Python + FastAPI + Pydantic v2 + SQLAlchemy 2.x
- **Database**: PostgreSQL 16
- **Cache**: Redis 7
- **Payments**: Razorpay (TEST MODE)
- **Migrations**: Alembic

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Node.js 20+
- Python 3.11+

### Local Development

```bash
# 1. Clone and configure
cp .env.example .env
# Edit .env with your Razorpay TEST keys

# 2. Start infrastructure
docker compose up -d postgres redis

# 3. Backend
cd backend
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt
alembic upgrade head
python -m app.seed  # Optional: seed demo data
uvicorn app.main:app --reload --port 8000

# 4. Frontend
cd frontend
npm install
npm run dev
```

### Docker Compose (Full Stack)

```bash
docker compose up --build
```

## Project Structure

```
flowmint-ai/
├── frontend/          # React SPA
├── backend/           # FastAPI application
├── docs/              # Architecture documentation
├── infrastructure/    # Docker, nginx configs
├── scripts/           # Dev utilities
├── tests/             # Test suites
├── .env.example
├── docker-compose.yml
└── README.md
```

## Phase 1 Scope

Core commerce flow without AI:

Merchant → Create Product → Set Inventory → Buyer Searches → Add to Cart → Create Order → Razorpay Payment → Webhook → Update State → Domain Event

## Documentation

- [Architecture](docs/architecture.md)
- [Database Design](docs/database-design.md)
- [API Contracts](docs/api-contracts.md)
- [Security](docs/security.md)
- [Testing](docs/testing.md)
- [Roadmap](docs/roadmap.md)

## License

Proprietary — All rights reserved.
