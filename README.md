# SvontAi - WhatsApp AI Business Assistant

SvontAi is a production-ready SaaS application that provides AI-powered WhatsApp assistants for businesses. It enables automated customer support, lead collection, and multi-channel communication through both WhatsApp and web chat widgets.

## 🚀 Features

- **AI-Powered Responses**: Uses OpenAI GPT models to generate human-like responses in Turkish
- **Multi-Tenant Architecture**: Each business gets isolated data and customizable bots
- **WhatsApp Integration**: Connect via WhatsApp Cloud API for automated messaging
- **Web Chat Widget**: Embeddable widget for websites with Shadow DOM isolation
- **Knowledge Base**: Train your bot with Q&A pairs specific to your business
- **Lead Collection**: Automatically capture customer information
- **Modern Dashboard**: Beautiful, responsive admin interface
- **n8n Workflow Engine**: Optional visual workflow automation for advanced use cases

## 📁 Project Structure

```
SvontAi/
├── backend/           # FastAPI backend
│   ├── app/
│   │   ├── api/       # API routes
│   │   ├── core/      # Config, security
│   │   ├── db/        # Database setup
│   │   ├── models/    # SQLAlchemy models
│   │   ├── schemas/   # Pydantic schemas
│   │   ├── services/  # Business logic
│   │   └── main.py    # App entry point
│   ├── alembic/       # Database migrations
│   └── requirements.txt
├── frontend/          # Next.js 14 dashboard
│   ├── src/
│   │   ├── app/       # App router pages
│   │   ├── components/
│   │   └── lib/       # Utils, API, store
│   └── package.json
├── widget/            # Vanilla JS chat widget
│   └── index.js
└── docs/              # Documentation
```

## 🛠 Tech Stack

### Backend
- Python 3.12
- FastAPI
- SQLAlchemy 2.x + PostgreSQL
- Alembic (migrations)
- JWT Authentication
- OpenAI API

### Frontend
- Next.js 14 (App Router)
- TypeScript
- TailwindCSS
- shadcn/ui components
- TanStack Query
- Zustand

### Widget
- Vanilla JavaScript
- Shadow DOM

## 🚀 Getting Started

### Prerequisites

- Python 3.12+
- Node.js 18+
- PostgreSQL 15+
- OpenAI API key

### Backend Setup

1. Navigate to backend directory:
```bash
cd backend
```

2. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create `.env` file (copy from `.env.example`):
```bash
cp .env.example .env
```

5. Configure environment variables:
```env
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/smartwa
JWT_SECRET_KEY=your-secret-key-change-this
OPENAI_API_KEY=sk-your-openai-key
WEBHOOK_USERNAME=your-webhook-username
WEBHOOK_PASSWORD=your-webhook-password
BOOTSTRAP_ADMIN_EMAIL=admin@yourdomain.com
ALLOW_ADMIN_PLAN_OVERRIDE=false
```

6. Create database:
```bash
createdb smartwa
```

7. Run migrations:
```bash
alembic upgrade head
```

8. Start server:
```bash
uvicorn app.main:app --reload
```

Backend will be available at `http://localhost:8000`
API docs at `http://localhost:8000/docs`

### Frontend Setup

1. Navigate to frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

3. Create `.env.local`:
```env
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
```

4. Start development server:
```bash
npm run dev
```

Frontend will be available at `http://localhost:3000`

### Widget Usage

Add this script to any website:
```html
<script
  src="http://localhost:8000/widget.js"
  data-bot-key="YOUR_BOT_PUBLIC_KEY"
  data-api-url="http://localhost:8000"
></script>
```

## 📱 WhatsApp Integration

SvontAi uses the official **Embedded Signup** flow:

1. Configure Meta App credentials (`META_APP_ID`, `META_APP_SECRET`, `META_REDIRECT_URI`)
2. Go to `/dashboard/setup/whatsapp`
3. Click **"WhatsApp'ı Bağla"** and complete the popup flow

See `docs/WHATSAPP_EMBEDDED_SIGNUP.md` for details.

## 🏠 Real Estate Pack (MVP)

Real Estate Pack adds sector-specific automation for real estate teams on top of the existing Tool Engine:
- WhatsApp lead segmentation + buyer/seller intent flow
- Listing matching + follow-up jobs + appointment flow
- Tenant-scoped settings/templates/analytics endpoints

Technical design and endpoint list: `docs/real_estate_pack.md`

## 🔒 Security

- JWT-based authentication with refresh tokens
- Password hashing with bcrypt
- CORS protection
- Input validation with Pydantic

## 📄 API Endpoints

### Authentication
- `POST /auth/register` - Register new user
- `POST /auth/login` - Login and get tokens
- `POST /auth/refresh` - Refresh access token

### Bots
- `GET /bots` - List all bots
- `POST /bots` - Create new bot
- `GET /bots/{id}` - Get bot details
- `PUT /bots/{id}` - Update bot
- `DELETE /bots/{id}` - Delete bot

### Knowledge Base
- `GET /bots/{id}/knowledge` - List knowledge items
- `POST /bots/{id}/knowledge` - Create knowledge item
- `PUT /bots/{id}/knowledge/{item_id}` - Update item
- `DELETE /bots/{id}/knowledge/{item_id}` - Delete item

### Public Chat
- `POST /public/chat/init` - Initialize chat session
- `POST /public/chat/send` - Send message and get response
- `GET /public/chat/messages` - Fetch conversation messages
- `POST /public/leads` - Submit lead information

### WhatsApp Webhook
- `GET /whatsapp/webhook` - Webhook verification
- `POST /whatsapp/webhook` - Receive messages
- `POST /webhooks/whatsapp` - Compatibility alias (HTTP Basic Auth required)

For `POST /webhooks/whatsapp` you must set:
- `WEBHOOK_USERNAME`
- `WEBHOOK_PASSWORD`

## 🚀 Deployment

### Backend (Railway/Render)
1. Set environment variables
2. Deploy from repository root (Railway reads root `requirements.txt` + `Procfile`)
3. Start command from `Procfile`:
```
web: cd backend && alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

#### Railway environment variables (minimum recommended)
```env
# Core
ENVIRONMENT=prod
DATABASE_URL=${{Postgres.DATABASE_URL}}
JWT_SECRET_KEY=change-this-to-a-secure-random-string
SUPER_ADMIN_REQUIRE_2FA=true
BOOTSTRAP_ADMIN_EMAIL=admin@yourdomain.com
ALLOW_ADMIN_PLAN_OVERRIDE=false

# URLs
FRONTEND_URL=https://<your-vercel-domain>
BACKEND_URL=https://<your-railway-domain>
WEBHOOK_PUBLIC_URL=https://<your-railway-domain>

# Email (required for register/forgot-password in prod)
EMAIL_ENABLED=true
EMAIL_PROVIDER=resend
RESEND_API_KEY=re_...
SMTP_FROM_EMAIL=no-reply@<your-domain>
SMTP_FROM_NAME=SvontAI

# Payments (Stripe - optional, enable when ready)
PAYMENTS_ENABLED=true
PAYMENTS_PROVIDER=stripe
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
# Optional convenience envs (monthly)
STRIPE_PRICE_ID_PRO=price_...
STRIPE_PRICE_ID_PREMIUM=price_...
# Optional billing portal return url
STRIPE_PORTAL_RETURN_URL=https://<your-vercel-domain>/dashboard/billing
# JSON mapping: plan -> interval -> price_id
STRIPE_PRICE_IDS='{"pro":{"monthly":"price_...","yearly":"price_..."},"premium":{"monthly":"price_...","yearly":"price_..."},"enterprise":{"monthly":"price_...","yearly":"price_..."}}'
STRIPE_SUCCESS_URL=https://<your-vercel-domain>/dashboard/billing?payment=success
STRIPE_CANCEL_URL=https://<your-vercel-domain>/dashboard/billing?payment=cancel

# Optional: OpenAI
OPENAI_API_KEY=sk-...

# Optional: WhatsApp Embedded Signup
META_APP_ID=...
META_APP_SECRET=...
META_CONFIG_ID=...
META_REDIRECT_URI=https://<your-railway-domain>/api/onboarding/whatsapp/callback
GRAPH_API_VERSION=v18.0

# Optional: Real Estate Pack automation
REAL_ESTATE_AUTOMATION_ENABLED=true
REAL_ESTATE_AUTOMATION_INTERVAL_SECONDS=300
REAL_ESTATE_WEEKLY_REPORT_DAY=0
REAL_ESTATE_WEEKLY_REPORT_HOUR_UTC=8

# Optional: Google Calendar OAuth (Real Estate Pack)
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REDIRECT_URI=https://<your-railway-domain>/real-estate/calendar/google/callback

# Optional: n8n
USE_N8N=false
SVONTAI_TO_N8N_SECRET=change-this-to-a-secure-random-string-svontai-to-n8n
N8N_TO_SVONTAI_SECRET=change-this-to-a-secure-random-string-n8n-to-svontai
# Tool runner debug (DNS/URL troubleshooting)
TOOL_RUNNER_DEBUG=false

# Tool Marketplace v1 - Artifact storage
ARTIFACT_STORAGE_PROVIDER=local
ARTIFACT_STORAGE_LOCAL_BASE_PATH=storage/artifacts
ARTIFACT_SIGNED_URL_EXPIRES_SECONDS=3600
ARTIFACT_SIGNING_SECRET=change-this-to-a-secure-random-string-artifacts

# If ARTIFACT_STORAGE_PROVIDER=supabase
SUPABASE_URL=https://<project>.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...
SUPABASE_STORAGE_BUCKET=svontai-artifacts
```

`SUPER_ADMIN_REQUIRE_2FA=true` olduğunda, Super Admin portalı girişleri için 2FA zorunlu olur.
`BOOTSTRAP_ADMIN_EMAIL` ilk açılışta sadece admin yoksa çalışır; belirtilen kullanıcıya global admin yetkisi verir.
`ALLOW_ADMIN_PLAN_OVERRIDE=true` ise prod ortamda `/admin/tenants/{tenant_id}/plan` endpoint’i aktif olur.
`TOOL_RUNNER_DEBUG=true` olduğunda `/tools/run` öncesi çözümlenen n8n URL/hostname/env snapshot loglanır (secret maskeli).

### Railway migration & smoke checklist (P6.1)

> Aşağıdaki sıra merge öncesi zorunlu doğrulama akışıdır.

#### 1) Pre-check (backup + alembic state)
```bash
# 1. Railway backend service'e bağlan
railway login
railway link

# 2. Production DB URL'yi doğrula (yerel shell'e export et)
export DATABASE_URL='postgresql+psycopg://...'

# 3. DB backup al (local)
pg_dump "$DATABASE_URL" -Fc -f "backup_pre_p6_$(date +%Y%m%d_%H%M%S).dump"

# 4. Mevcut alembic version kontrol
cd backend
alembic current
alembic heads
```

#### 2) Deploy + migrations
```bash
# Repo root
git push origin <branch>

# Railway deploy
railway up
```

`Procfile` start komutu migration içerir:
```bash
cd backend && alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

#### 3) Post-migration doğrulama
```bash
# Backend container içinde kontrol (Railway shell)
railway shell
cd backend
alembic current
alembic heads
```
Beklenen: `alembic current` çıktısı `heads` ile aynı revision (`029`).

#### 4) Route registration + app boot doğrulama
```bash
curl -fsS https://<your-railway-domain>/health
curl -fsS https://<your-railway-domain>/openapi.json | jq '.paths["/integrations/status"], .paths["/tools/run"], .paths["/tools/runs/{request_id}"]'
```

### Lightweight smoke script (pytest bağımsız)

Dosya: `scripts/smoke_tool_engine.py`

Çalıştırma:
```bash
python3 scripts/smoke_tool_engine.py
```

Opsiyonel env:
```bash
# default: http://127.0.0.1:8000
export SMOKE_BASE_URL=https://<your-railway-domain>

# hazır token/tenant ile koşmak için:
export SMOKE_ACCESS_TOKEN=...
export SMOKE_TENANT_ID=...

# register/login flow için:
export SMOKE_EMAIL=smoke@example.com
export SMOKE_PASSWORD=Password123!
export SMOKE_VERIFICATION_CODE=123456   # yalnızca response'tan code parse edilemezse
```

Script adımları:
1. `/health` (fallback `/`) ile servis ayakta mı kontrol eder.
2. Token+tenant üretir (register + email verify + login + tenant create/resolve).
3. `GET /integrations/status`
4. `GET /tools`
5. `PUT /tools/pdf_summary/settings` (`enabled=true`)
6. `POST /tools/run` (dummy `requestId`)
7. `GET /tools/runs` ve `GET /tools/runs/{request_id}`

`USE_N8N=false` ise `/tools/run` `success=false` dönebilir; bu durumda smoke script endpoint/DB zinciri çalıştıysa testi geçerli kabul eder.

### Migration 029 safety notes

- Migration: `backend/alembic/versions/029_standardize_plans_and_add_google_oauth_tokens.py`
- Değişiklikler:
  - `google_oauth_tokens` tablosu eklenir.
  - Eski plan adları normalize edilir:
    - `starter -> pro`
    - `pro -> premium` (legacy veri durumuna göre)
    - `business -> enterprise`
  - `tenant_subscriptions.plan_id` plan merge durumlarında yeni plana taşınır.
  - `tools.required_plan` legacy değerleri normalize edilir (`starter/growth/business`).
- Not: plan birleştirme/rename operasyonları nedeniyle downgrade teorik olarak mümkün olsa da **tam kayıpsız geri dönüş garantisi yoktur**. Merge öncesi DB backup zorunlu.

Rollback (acil durum):
```bash
# uygulamayı bakım moduna al
alembic downgrade 028

# gerekirse backup restore
pg_restore --clean --if-exists --no-owner --no-privileges -d "$DATABASE_URL" backup_pre_p6_<timestamp>.dump
```

### Post-deploy verification (expected)

- `GET /health` -> `200`
- `GET /integrations/status` -> `200`, Google integration alanları:
  - `connected` / `missing` / `expired`
  - `required_scopes`, `granted_scopes`, `expires_at`
- `GET /tools` -> `200`, her tool için `requiredPlan` gelir.
- `PUT /tools/{slug}/settings` -> `200`
- `POST /tools/run` -> `200` (`requestId` echo, run kaydı oluşur)
- `GET /tools/runs` -> `200`
- `GET /tools/runs/{request_id}` -> `200`

### Frontend (Vercel)
1. Connect GitHub repository
2. Set `NEXT_PUBLIC_BACKEND_URL`
3. Deploy

#### Vercel environment variables
```env
NEXT_PUBLIC_BACKEND_URL=https://<your-railway-domain>
```

### Widget
Serve `widget/index.js` via CDN or backend static files.

## 🔄 n8n Workflow Engine (Optional)

SvontAI can integrate with n8n for visual workflow automation:

```bash
# Start with n8n enabled
docker compose up -d

# Access n8n dashboard
open http://localhost:5678
```

Configure in `.env`:
```env
USE_N8N=true
N8N_INCOMING_WORKFLOW_ID=svontai-incoming
SVONTAI_TO_N8N_SECRET=your-secure-random-secret-1
N8N_TO_SVONTAI_SECRET=your-secure-random-secret-2
```

Tool Marketplace API (tenant auth required):
- `GET /tools`
- `GET /tools/runs`
- `GET /tools/runs/{request_id}`
- `POST /tools/run`

Admin Tools API (super admin token required):
- `GET /admin/tools`
- `GET /admin/tools/{tool_id}`
- `PATCH /admin/tools/{tool_id}`
- `PUT /admin/tools/{tool_id}`

Tool workflow ID güncelleme örneği:
```bash
curl -X PATCH "https://<your-railway-domain>/admin/tools/<tool_id>" \
  -H "Authorization: Bearer <SUPER_ADMIN_ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"n8n_workflow_id":"svontai-meeting-summary"}'
```

Billing API (tenant auth required except webhook):
- `GET /billing/plan`
- `GET /billing/limits`
- `POST /billing/stripe/checkout-session`
- `GET /billing/stripe/portal`
- `POST /billing/stripe/webhook` (Stripe signature required)

### Key Features

- **Async Webhook Processing**: WhatsApp webhooks return HTTP 200 immediately. n8n workflow triggers run in background tasks to ensure Meta's 20-second timeout is never exceeded.
- **Idempotency**: Duplicate messages (same `tenant_id` + `message_id`) are automatically detected and ignored. Safe for webhook retries.
- **Production Security**: Default secrets are rejected at startup in production (`ENVIRONMENT=prod`). Generate secure secrets with: `python -c "import secrets; print(secrets.token_urlsafe(32))"`
- **Retry with Backoff**: Failed n8n triggers are retried with exponential backoff.

See `docs/N8N_INTEGRATION.md` for detailed setup guide.

### Security Notes

⚠️ **Production Checklist:**

1. **Change all default secrets** - The app will refuse to start in production with insecure defaults
2. **Use HTTPS** - All webhook and callback URLs must use HTTPS
3. **Verify webhook signatures** - Meta webhook signatures should be verified (configurable)
4. **Set proper CORS origins** - Restrict to your domains only

## 📝 License

MIT License

## 🤝 Contributing

Contributions are welcome! Please read our contributing guidelines first.
