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
<script src="http://localhost:8000/widget.js" data-bot-key="YOUR_BOT_PUBLIC_KEY"></script>
```

## 📱 WhatsApp Integration

1. Create a Meta Business account
2. Set up WhatsApp Business API
3. Configure webhook URL: `https://your-backend-url/whatsapp/webhook`
4. Add your credentials in the bot settings

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
- `POST /public/leads` - Submit lead information

### WhatsApp Webhook
- `GET /whatsapp/webhook` - Webhook verification
- `POST /whatsapp/webhook` - Receive messages

## 🚀 Deployment

### Backend (Railway/Render)
1. Set environment variables
2. Deploy with `Procfile`:
```
web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

### Frontend (Vercel)
1. Connect GitHub repository
2. Set `NEXT_PUBLIC_BACKEND_URL`
3. Deploy

### Widget
Serve `widget/index.js` via CDN or backend static files.

## 📝 License

MIT License

## 🤝 Contributing

Contributions are welcome! Please read our contributing guidelines first.

