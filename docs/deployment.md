# Flowmint AI — Deployment Guide & Staging Architecture

This guide describes how to configure, deploy, and verify Flowmint AI in cloud staging and production environments.

---

## 🏗️ Architecture Topology

| Component | Staging / Cloud Target | Technology | Configuration / Role |
| :--- | :--- | :--- | :--- |
| **Frontend SPA** | Vercel | React 18 + Vite + Tailwind | Static CDN distribution with client-side SPA routing (`vercel.json`) |
| **Backend API** | Render / AWS ECS | Python 3.11 + FastAPI + Uvicorn | Async ASGI server (`render.yaml` or `Dockerfile`) |
| **Primary Database** | Managed PostgreSQL 15+ | Neon / Render Postgres / AWS RDS | ACID relational storage, composite multi-tenant constraints, Alembic migrations |
| **Cache & Bus** | Managed Redis 7+ | Upstash / Render Redis / AWS ElastiCache | Idempotency locks, safe read caching, rate limiting, and pub/sub |
| **AI Inference** | Cloud LLM Provider | OpenAI GPT-4o / Google Gemini 1.5 Flash / Anthropic | Structured tool calling, intent routing, and investigation |
| **Payments Gateway** | Razorpay TEST Mode | Razorpay Payments API | Order checkout, test payment capture, and webhook signature verification |

---

## 🔒 Production Security & Secrets Checklist

Before starting in `APP_ENV=production` or `APP_ENV=staging`, the backend configuration automatically verifies:

1. **`SECRET_KEY` and `JWT_SECRET_KEY`:**
   - Must be strong cryptographically generated strings (min 16 characters).
   - Insecure defaults (`change-me`, `dev-secret-key`) cause startup failure.
2. **`DATABASE_URL`:**
   - Must point to an authenticated managed cloud database.
   - Default credentials (`flowmint_dev`) are rejected at startup.
3. **`DEBUG` Mode:**
   - Must be set to `false`.
4. **Zero Secret Leakage:**
   - Secrets and tokens are filtered by `redact_sensitive_data` before logging.
   - API error responses return generic messages (`INTERNAL_ERROR`) without leaking internal traces or stack traces.

---

## 🚀 Step 1: Backend Staging on Render

A preconfigured `render.yaml` Blueprint is included in the project root.

1. In Render Dashboard, click **New +** &rarr; **Blueprint**.
2. Connect your Git repository. Render will automatically parse `render.yaml` and provision:
   - `flowmint-ai-backend` (Web Service)
   - `flowmint-db` (PostgreSQL Database)
   - `flowmint-redis` (Redis Instance)
3. Set the required environment variables:
   ```bash
   APP_ENV=staging
   DEBUG=false
   RAZORPAY_KEY_ID=rzp_test_...
   RAZORPAY_KEY_SECRET=...
   RAZORPAY_WEBHOOK_SECRET=...
   AI_PROVIDER=google   # or openai
   GOOGLE_API_KEY=...   # or OPENAI_API_KEY
   ```
4. Render automatically executes `alembic upgrade head` before starting Uvicorn.
5. Verify health:
   ```bash
   curl -i https://flowmint-ai-backend.onrender.com/api/v1/health
   ```
   Expected response:
   ```json
   {"success":true,"data":{"status":"healthy","service":"flowmint-ai","app_env":"staging"},"errors":null}
   ```

---

## 🌐 Step 2: Frontend Staging on Vercel

1. In Vercel Dashboard, click **Add New Project** &rarr; **Import Git Repository**.
2. Set Root Directory to `frontend`.
3. Build Settings:
   - Framework Preset: **Vite**
   - Build Command: `npm run build`
   - Output Directory: `dist`
4. Set Environment Variables:
   ```bash
   VITE_API_URL=https://flowmint-ai-backend.onrender.com/api/v1
   ```
5. Deploy. `frontend/vercel.json` ensures client-side routing fallback to `/index.html` and sets HTTP security headers (`nosniff`, `DENY` framing, XSS protection).

---

## 🧪 Step 3: Staging Verification Smoke Tests

Once deployed, run the canonical verification workflow:

1. **Merchant Authentication:** Register and log in as store owner.
2. **Product & Cart Creation:** Add products to storefront, create a customer cart.
3. **Razorpay TEST Workflow:** Complete a test checkout using Razorpay test card credentials.
4. **Webhook Delivery:** Send payment capture webhook with signature verification.
5. **Opportunity Detection:** Verify abandoned cart or payment retry opportunity appears.
6. **HITL Governance:** Approve action plan and verify idempotent execution.
7. **Attribution:** Confirm `OBSERVED` outcome and `DETERMINISTIC EVENT LINK`.
