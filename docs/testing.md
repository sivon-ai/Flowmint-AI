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
| Governance & Execution | Policy rules, risk classification, approval expiration, idempotency locks, audit log immutability |
| Evaluation & Attribution | 900-case dataset structure, MockLLM vs Real LLM runner, revenue attribution ledger, before-vs-after reporting, DAG trace reconstruction, 5 fail-closed recovery scenarios, 10 red-team adversarial scenarios, performance metrics, canonical 5-minute success demo, mandatory policy blocked demo |

### Phase 4 Evaluation Dataset Breakdown
- **500 Buyer Queries**: Faceted search, filtering, inventory, cart mutations.
- **100 Analytics Queries**: Revenue aggregations, conversion metrics, payment failures, comparisons.
- **100 Growth Scenarios**: Bundle recommendations, cross-sell offers.
- **50 Recovery Scenarios**: Abandoned cart recoveries, payment retry nudges.
- **50 Adversarial Bypass Scenarios**: Discounts > 15%, budget overruns, negative prices.
- **50 Prompt Injection Scenarios**: Jailbreaks, system instruction extraction, fake approval claims.
- **50 Failure Scenarios**: Malformed parameters, empty states, missing targets.

### Verified Status: 124/124 Tests Passing
- 124 backend tests passing with pytest.
- Vitest frontend tests passing.
- TypeScript `tsc --noEmit` passing with 0 errors.
- Production bundle compiled cleanly.

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
