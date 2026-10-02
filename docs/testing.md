# Flowmint AI — Testing Strategy

## Backend Testing

### Framework
- **pytest** + **pytest-asyncio** for async tests
- **httpx** AsyncClient for API tests
- **SQLAlchemy** test sessions with table create/drop per test

### Test Categories

| Category | Coverage |
|---|---|
| Auth | Registration, login, duplicate email, wrong password, token refresh, protected routes |
| Products | CRUD, search, duplicate SKU detection, attribute management |
| Tenant Isolation | Cross-merchant product access denied, list isolation |
| Inventory | Get, update, reservation (Phase 1 through orders) |
| Cart | Full lifecycle: create → add items → update → remove |
| Orders | Create from cart, empty cart rejection, inventory reservation |
| Payment State | Valid/invalid transitions, state machine completeness |
| Webhook Security | Invalid signature rejection, no-JWT requirement |
| Outbox | Product creation creates outbox event |
| Health | Liveness endpoint |
| AI Providers | MockLLMProvider conversational & tool routing, preset queues, provider factory, embedding dimensions |
| AI Tools | Registry schema generation, parameter validation, tool execution latency, disallowed tool rejection, mutating tool rejection |
| Buyer Agent | Catalog search, empty catalog anti-hallucination, real-time inventory checking |
| Analytics Agent | Revenue calculation, AOV, order status summary, product sales ranking |
| Agent Orchestrator | Deterministic intent routing across 40 fixture queries, clarification requests, session/run lifecycle persistence |
| Prompt Injection | Adversarial jailbreak detection, tenant isolation in tools, untrusted data wrapping |
| Agent API | Endpoints `/chat`, `/buyer`, `/analytics`, `/sessions`, `/runs`, cross-tenant session access denial |

### Fixture Dataset (`tests/ai/fixtures.py`)
- **20 Buyer Queries**: Testing product retrieval, budget constraints, feature filtering, and catalog queries.
- **10 Analytics Queries**: Testing revenue aggregations, conversion metrics, product rankings, and period comparisons.
- **10 Adversarial Queries**: Testing prompt injection resistance, role overrides, system instruction extraction, and tool bypass attempts.

### Running Tests
```bash
cd backend
.venv\Scripts\activate
pytest tests/ -v
```

## Frontend Testing

### Framework
- **Vitest** for unit/component tests
- **React Testing Library** for component testing
- **Playwright** for E2E (Phase 4)

### Running Tests
```bash
cd frontend
npm test
```

## Test Data

- Test fixtures in `tests/conftest.py` create fresh data per test
- Tables are created/dropped for each test (isolation)
- Two merchant fixtures (`merchant`, `merchant_b`) for tenant isolation tests
- Seed data script (`python -m app.seed`) for demo/development

## CI Integration (Future)

```yaml
# GitHub Actions outline
test-backend:
  - Setup Python 3.11
  - Start PostgreSQL service
  - pip install -r requirements.txt
  - alembic upgrade head
  - pytest tests/ -v --cov

test-frontend:
  - Setup Node 20
  - npm ci
  - npm run test
  - npm run build
```
