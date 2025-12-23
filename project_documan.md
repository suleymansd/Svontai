You are a senior full-stack architect, product designer, and UX engineer.

Build a **production-ready SaaS application** called **SvontAi – WhatsApp İşletme AI Asistanı**.

The goal of SvontAi:
- For any business (tenant), provide an **AI-powered WhatsApp assistant** that:
  - Receives incoming WhatsApp messages from customers.
  - Uses a tenant-specific knowledge base and OpenAI to generate human-like replies in Turkish (and multi-language later).
  - Can ask for and collect lead information (name, email, phone).
  - Logs conversations and leads into a dashboard.
  - Optionally also provides a web chat widget using the same bot.

This prompt should result in a full project skeleton with:
- Backend (FastAPI)
- Frontend dashboard (Next.js 14 App Router, TypeScript, TailwindCSS, shadcn/ui)
- Public web widget (vanilla JS with Shadow DOM)
- WhatsApp Cloud API webhook integration
- OpenAI integration
- Clean architecture, clear folders, reusable components, and **excellent UX / UI**.

Be opinionated and make good defaults. If something is ambiguous, make a reasonable assumption and document it in comments or README.

----------------------------------------------------
## 1. OVERALL ARCHITECTURE

Create a **monorepo style** structure (you can assume single repo) like:

- `/backend`  → FastAPI app
- `/frontend` → Next.js app (dashboard + marketing site)
- `/widget`   → vanilla JS chat widget bundle
- `/infrastructure` (optional) → config, deployment notes, env examples
- `/docs`     → high-level README, API docs, architecture notes (basic)

Focus on:
- Clear separation of concerns.
- Multi-tenant SaaS pattern (each business is a tenant).
- Extendability for future features (billing, message limits, vector search).

----------------------------------------------------
## 2. TECHNOLOGY STACK

### Backend
- Python 3.12
- FastAPI
- SQLAlchemy 2.x (ORM)
- PostgreSQL
- Alembic (migrations)
- Pydantic v2
- JWT authentication (access + refresh tokens)
- Optional: Redis for rate limiting and caching (design structure, stub usage)

### Frontend
- Next.js 14 – App Router, TypeScript
- React 18
- TailwindCSS
- shadcn/ui component library
- TanStack Query (React Query) for data fetching
- Axios or Fetch wrapper
- Zustand for lightweight global state (auth, layout, theme)

### AI
- OpenAI Chat Completions API (gpt-4.1 or gpt-4.1-mini)
- Simple prompt-based knowledge usage (MVP: no vector DB, just structured prompt)
- Write AI service in backend: `services/ai_service.py`

### WhatsApp
- Meta WhatsApp Cloud API
- Webhook endpoint to receive messages
- Outgoing message sender using WhatsApp API
- Ability to configure WhatsApp credentials per tenant

### Widget
- Pure, framework-less JavaScript
- Shadow DOM to avoid CSS conflicts
- Mobile-friendly chat bubble UI
- Configurable brand color and position (left/right)
- Communicates with backend public chat endpoints via fetch.

### Deployment (just prepare structure and config hints)
- Backend: Railway (or any container platform)
- Frontend: Vercel
- Database: PostgreSQL (managed)
- Env config via `.env` files

----------------------------------------------------
## 3. DOMAIN MODEL & DATABASE DESIGN

Implement a **multi-tenant** data model.

### Tables / Models

**User**
- `id` (UUID, PK)
- `email` (unique, indexed)
- `password_hash`
- `full_name`
- `created_at`
- `updated_at`
- Relation to tenants: one user can own or belong to multiple tenants (for MVP, you can assume 1 owner per tenant, but design for N:1 easily).

**Tenant**
- `id` (UUID, PK)
- `name`
- `owner_id` (FK → User)
- `created_at`
- `updated_at`
- Settings JSON (for future use)

**Bot**
- `id` (UUID, PK)
- `tenant_id` (FK → Tenant)
- `name`
- `description`
- `welcome_message`
- `language` (e.g. "tr", "en")
- `primary_color` (string hex, e.g. "#3C82F6")
- `widget_position` (enum: "right" | "left")
- `public_key` (unique string used by widget/public endpoints)
- `is_active` (bool)
- `created_at`
- `updated_at`

**BotKnowledgeItem**
- `id` (UUID, PK)
- `bot_id` (FK → Bot)
- `title`
- `question`
- `answer`
- `created_at`

**WhatsAppIntegration**
- `id` (UUID, PK)
- `tenant_id` (FK → Tenant)
- `bot_id` (FK → Bot, nullable if global for tenant)
- `whatsapp_phone_number_id`
- `whatsapp_business_account_id`
- `access_token` (encrypted or stored securely)
- `webhook_verify_token`
- `is_active`
- `created_at`
- `updated_at`

**Conversation**
- `id` (UUID, PK)
- `bot_id` (FK → Bot)
- `external_user_id` (string, unique per external source)
- `source` (enum: "whatsapp" | "web_widget")
- `created_at`
- `updated_at`
- `metadata` (JSON)

**Message**
- `id` (UUID, PK)
- `conversation_id` (FK → Conversation)
- `sender` (enum: "user" | "bot" | "system")
- `content` (text)
- `created_at`
- Optional: `raw_payload` JSON (for debugging)

**Lead**
- `id` (UUID, PK)
- `bot_id` (FK → Bot)
- `conversation_id` (FK → Conversation, nullable)
- `name`
- `email`
- `phone`
- `notes`
- `created_at`

Design SQLAlchemy models + Pydantic schemas for these entities.

----------------------------------------------------
## 4. BACKEND STRUCTURE & ENDPOINTS

Folder structure (backend):

- `backend/app/main.py`
- `backend/app/core/` (config, security, auth utils)
- `backend/app/db/` (session, base, init, migrations)
- `backend/app/models/`
- `backend/app/schemas/`
- `backend/app/api/routers/`
- `backend/app/services/` (ai_service, whatsapp_service, lead_service, etc.)
- `backend/app/dependencies/`

### Config & Settings

Create a Pydantic `Settings` class:

- `DATABASE_URL`
- `JWT_SECRET_KEY`
- `JWT_ALGORITHM`
- `ACCESS_TOKEN_EXPIRE_MINUTES`
- `REFRESH_TOKEN_EXPIRE_DAYS`
- `OPENAI_API_KEY`
- `WHATSAPP_BASE_URL` (e.g. https://graph.facebook.com/v17.0)
- `BACKEND_URL`
- `FRONTEND_URL`
- `ENVIRONMENT` ("dev" | "prod")

Use dependency injection to access settings.

### Authentication

JWT based auth:
- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/refresh`

Use:
- Access token: short-lived
- Refresh token: longer-lived
- Password hashing: `passlib` (bcrypt)
- Protect private routes using `Depends(get_current_user)`.

### Tenant & User

- `GET /me` → current user info + associated tenant(s)
- `POST /tenants` → create tenant
- `GET /tenants/my` → list tenants for current user (for MVP, one is enough)

### Bot Management

- `GET /bots` (list bots of current tenant)
- `POST /bots` → create bot
- `GET /bots/{bot_id}`
- `PUT /bots/{bot_id}`
- `DELETE /bots/{bot_id}`

On creation:
- Generate a unique `public_key` (for widget + public chat).

### Knowledge Base

- `GET /bots/{bot_id}/knowledge`
- `POST /bots/{bot_id}/knowledge`
- `PUT /bots/{bot_id}/knowledge/{item_id}`
- `DELETE /bots/{bot_id}/knowledge/{item_id}`

These items will be used to build the AI prompt.

### WhatsApp Integration

- `POST /bots/{bot_id}/whatsapp-integration` → save connection credentials
- `GET /bots/{bot_id}/whatsapp-integration`

Webhook endpoints:
- `GET /whatsapp/webhook` → verification (respond to challenge when verify_token matches)
- `POST /whatsapp/webhook` → receive inbound message events

Flow:
1. On inbound WhatsApp message:
   - Identify tenant and bot from integration data (phone_number_id, etc.).
   - Find or create `Conversation` with `source="whatsapp"` and external user id (WhatsApp user phone).
   - Save user `Message`.
   - Use `ai_service.generate_reply(bot, knowledge_items, conversation, last_user_message)` to get answer.
   - Save bot `Message`.
   - Use `whatsapp_service.send_message()` to send reply back.
2. Optionally detect lead info in messages (for MVP, keep manual lead creation via dashboard).

### Public Web Widget Chat

Endpoints:
- `POST /public/chat/init`
  - Input: `bot_public_key`, optional `external_user_id`
  - Behavior:
    - Find active bot with given public_key.
    - If external_user_id not provided, generate and return one.
    - Create or retrieve `Conversation` for this external user.
    - Return:
      - `conversation_id`
      - `external_user_id`
      - `bot` public info (name, color, position)
      - `welcome_message`.

- `POST /public/chat/send`
  - Input: `conversation_id`, `message`
  - Behavior:
    - Save user message.
    - Load bot and knowledge items.
    - Call AI service.
    - Save bot message.
    - Return bot reply.

**Leads public:**
- `POST /public/leads`
  - Input: `bot_public_key`, `name`, `email`, `phone`, optional `conversation_id`
  - Save Lead for this bot.

### Conversation & Message Logs (Dashboard)

Protected endpoints:
- `GET /bots/{bot_id}/conversations`
- `GET /conversations/{conversation_id}/messages`
- `GET /bots/{bot_id}/leads`

Allow pagination and filters.

----------------------------------------------------
## 5. AI SERVICE DESIGN

Create a service in `backend/app/services/ai_service.py` like:

- `async def generate_reply(bot, knowledge_items, conversation, last_user_message: str) -> str:`

Prompt template (simplified):

SYSTEM (in Turkish, but keep flexible):

"Sen bir işletmenin müşteri destek asistanısın. 
Sadece aşağıdaki bilgi tabanına ve konuşma geçmişine dayanarak cevap ver. 
Emin değilsen açıkça belirt ve insan desteğe yönlendir. 
Kısa, net ve nazik yanıt ver. Emoji kullanımı sınırlı olsun."

Then:
- Include a formatted section with knowledge items: title, question, answer.
- Include last N messages from conversation as context.
- Then user’s last question as "USER: ...".

Call OpenAI Chat Completions API via async HTTP client or official SDK.
Keep API key in env.

----------------------------------------------------
## 6. FRONTEND – NEXT.JS DASHBOARD & MARKETING

Build a **modern, clean, professional SaaS UI**.

Use:
- Next.js App Router
- TypeScript
- TailwindCSS
- shadcn/ui components (Button, Card, Input, Textarea, Tabs, Table, Dialog, Badge, Tooltip, etc.)
- TanStack Query for data fetching and caching
- Zustand store for auth and layout states

### Layout & Navigation

General layout:

- A public marketing area:
  - `/` (Landing page)
  - `/pricing`
  - `/login`
  - `/register`

- An authenticated dashboard area under `/dashboard`:
  - `/dashboard` (overview)
  - `/dashboard/bots`
  - `/dashboard/bots/[botId]`
  - `/dashboard/bots/[botId]/knowledge`
  - `/dashboard/bots/[botId]/conversations`
  - `/dashboard/leads`
  - `/dashboard/settings` (profile, tenant, WhatsApp config)

Use a **left sidebar layout**:

Sidebar sections:
- Overview
- Bots
- Knowledge
- Conversations
- Leads
- Settings

Top bar:
- Tenant name
- User profile dropdown
- Theme toggle (light/dark)
- Simple breadcrumb.

### Design Language (UI / UX):

- Use lots of white space and padding.
- Components with large rounded corners (`rounded-2xl`).
- Soft shadows for cards.
- Font sizes: 
  - Title: `text-2xl` / `text-3xl`, 
  - Subtitles: `text-lg`,
  - Body: `text-sm` / `text-base`.
- Use a primary blue color (#3C82F6) but keep it configurable.
- Hover transitions on buttons and cards (`transition`, `duration-200`, `hover:shadow-md`, slight `hover:-translate-y-[1px]`).
- Use skeleton loaders when data is loading.
- Show clear empty states:
  - "Henüz bir bot oluşturmadınız."
  - "Bilgi tabanınız boş. Başlamak için ilk Q&A’nizi ekleyin."
  - "Henüz lead yok."

UX principles:
- Make forms simple, group related fields.
- Show inline validation errors.
- Confirm destructive actions with modals.
- Optimistic updates where suitable.

### Pages Details

**Landing Page `/`**
- Hero section:
  - Title: “WhatsApp işletme mesajlarına 7/24 cevap veren yapay zeka asistanı.”
  - Subtitle: “SvontAi, işletmeniz için özel eğitilen WhatsApp AI asistanıdır. Müşteri sorularını yanıtlar, randevu alır, lead toplar.”
  - CTA Buttons: “Demo Talep Et”, “Hemen Başla”
- Feature section:
  - Cards for:
    - 24/7 Yanıt
    - Lead Toplama
    - Bilgi Tabanı ile Eğitme
    - WhatsApp + Web Widget
- Pricing teaser section (Starter / Pro / Business)
- Simple FAQ section.

**Auth Pages `/login`, `/register`**
- Centered card layout.
- Use email + password.
- Show simple validation.
- On success, redirect to `/dashboard`.

**Dashboard Overview `/dashboard`**
- Show:
  - Total bots
  - Total conversations (last 7 days)
  - Total leads
  - Simple line chart (use e.g. recharts if you want) or just placeholder for now.
- Recently active conversations list.

**Bots List `/dashboard/bots`**
- Table or cards of bots:
  - Name
  - Status (Active/Inactive)
  - Created date
  - Quick actions (Edit, View, Copy widget code)
- Button "Yeni Bot Oluştur".

**Bot Edit `/dashboard/bots/[botId]`**
- Two-column layout on desktop:
  - Left: Form fields for:
    - Name
    - Description
    - Welcome message
    - Primary color (color input)
    - Widget position (radio: left/right)
    - Language (dropdown)
  - Right: Live preview of web widget inside a frame (mocked using local UI component; call actual widget later).
- Show code snippet block (copyable):
  - `<script src="https://your-domain.com/widget.js" data-bot-key="PUBLIC_KEY"></script>`

**Knowledge Base `/dashboard/bots/[botId]/knowledge`**
- Table:
  - Title
  - Question
  - Answer (truncated)
  - Created date
  - Actions (Edit/Delete)
- Dialog/modal to add/edit knowledge items:
  - Fields: title, question, answer (textarea).
- Empty state with a call to action.

**Conversations `/dashboard/bots/[botId]/conversations`**
- List of conversations:
  - Source (WhatsApp / Web)
  - External user id (masked)
  - Last message preview
  - Updated time
- Click to open a conversation detail view:
  - Chat-like interface:
    - Left side: message list (user vs bot bubbles).
    - Right side: conversation metadata (source, lead status, tags - placeholder).
  - Optionally allow operator to send manual messages (post to WhatsApp later).

**Leads `/dashboard/leads`**
- Filterable table:
  - Name
  - Email
  - Phone
  - Bot name
  - Created date
- Search bar by name/email/phone.
- "Export CSV" button (can just generate simple CSV in frontend for now).

**Settings `/dashboard/settings`**
- Tabs:
  - Profile: name, email.
  - Tenant: tenant name.
  - WhatsApp Integration: show fields to configure:
    - Phone number ID
    - Business Account ID
    - Access token
    - Webhook verify token
  - For WhatsApp: show the webhook URL that user must paste into Meta console (derived from BACKEND_URL).

----------------------------------------------------
## 7. WIDGET (VANILLA JS + SHADOW DOM)

In `/widget`, build:

- `index.js` – main entry (bundle entrypoint)
- `styles.css` – styles used inside shadow root only

Behavior:

- The script is included on customer websites as:

  `<script src="https://your-domain.com/widget.js" data-bot-key="PUBLIC_KEY"></script>`

- On load:
  - Read `data-bot-key`.
  - Create a floating circular chat button at bottom-right by default.
  - On click, open a chat window:
    - Container attached to `document.body`, but UI inside a Shadow DOM root.
    - Chat header: bot name, close button.
    - Chat body: messages.
    - Input box and send button.
- On first open:
  - Call `POST /public/chat/init` with `bot_public_key` and any stored `external_user_id` from `localStorage`.
  - Save `conversation_id` and `external_user_id` in `localStorage`.

- On send:
  - Append user bubble to UI.
  - Call `POST /public/chat/send` with `conversation_id` and message.
  - Show typing indicator.
  - On reply, append bot bubble.

Styles:
- Rounded card, subtle shadow.
- Mobile-responsive (for small screens, full width at bottom).
- Uses primary_color from backend response to style header and button.
- Avoid leaking styles to parent page using Shadow DOM.

----------------------------------------------------
## 8. ENV & CONFIG

Create `.env.example` files for backend and frontend.

Backend `.env.example`:

- `DATABASE_URL=postgresql+psycopg://user:password@hostname:5432/dbname`
- `JWT_SECRET_KEY=`
- `JWT_ALGORITHM=HS256`
- `ACCESS_TOKEN_EXPIRE_MINUTES=30`
- `REFRESH_TOKEN_EXPIRE_DAYS=14`
- `OPENAI_API_KEY=`
- `WHATSAPP_BASE_URL=https://graph.facebook.com/v17.0`
- `BACKEND_URL=http://localhost:8000`
- `FRONTEND_URL=http://localhost:3000`

Frontend `.env.local.example`:

- `NEXT_PUBLIC_BACKEND_URL=http://localhost:8000`

Add basic instructions in a `/docs/SETUP.md` file on:
- How to run backend (uvicorn).
- How to run migrations (alembic).
- How to run frontend (next dev).
- How to build widget and serve it via backend or separate static hosting.

----------------------------------------------------
## 9. CODE QUALITY & ORGANIZATION

General requirements:

- Type-safe, clean, well-structured.
- Add docstrings to services and critical functions.
- Use consistent naming conventions.
- Use async endpoints in FastAPI.
- Use React Server Components + client components where appropriate in Next.js.
- Create reusable UI components:
  - `DashboardShell`
  - `PageHeader`
  - `StatCard`
  - `DataTable` or at least Table wrappers
  - `EmptyState`

Add comments where a human developer must plug in real secrets or Meta console configurations.

----------------------------------------------------
## 10. WHAT TO GENERATE NOW

Based on this specification, generate for me:

1. The **backend** scaffold:
   - `main.py` with FastAPI app and router includes.
   - Models, schemas, routers for:
     - auth
     - tenants
     - bots
     - knowledge
     - conversations
     - leads
     - public chat
     - whatsapp webhook
   - `services/ai_service.py` and `services/whatsapp_service.py` stubs with core logic.
   - Database setup and an initial Alembic migration.

2. The **frontend** scaffold:
   - Next.js App Router structure with pages and layout.
   - Basic shadcn/ui integration.
   - Example pages for:
     - `/`
     - `/login`
     - `/register`
     - `/dashboard` and nested routes.
   - React Query hooks for calling backend endpoints (create API client wrapper).
   - Core UI components for good UX (cards, tables, empty states, forms).

3. The **widget** scaffold:
   - A single `index.js` file that:
     - Reads `data-bot-key`
     - Creates floating button
     - Mounts a chat widget via Shadow DOM
     - Calls backend public chat endpoints.

4. Short README or SETUP notes (in English) at repo root explaining:
   - What the project is.
   - How to run backend + frontend.
   - How to build and include widget.

Be explicit, modular, and production-minded. Prioritize **excellent UX**, clean architecture, and extendability .