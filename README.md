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

# Optional: OpenAI
OPENAI_API_KEY=sk-...

# Optional: WhatsApp Embedded Signup
META_APP_ID=...
META_APP_SECRET=...
META_CONFIG_ID=...
META_REDIRECT_URI=https://<your-railway-domain>/api/onboarding/whatsapp/callback
GRAPH_API_VERSION=v18.0

# Optional: n8n
USE_N8N=false
SVONTAI_TO_N8N_SECRET=change-this-to-a-secure-random-string-svontai-to-n8n
N8N_TO_SVONTAI_SECRET=change-this-to-a-secure-random-string-n8n-to-svontai
```

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
