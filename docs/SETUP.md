# SvontAi Setup Guide

This guide will walk you through setting up SvontAi for development.

## Prerequisites

- **Python 3.12+**: [Download Python](https://www.python.org/downloads/)
- **Node.js 18+**: [Download Node.js](https://nodejs.org/)
- **PostgreSQL 15+**: [Download PostgreSQL](https://www.postgresql.org/download/)
- **OpenAI API Key**: [Get API Key](https://platform.openai.com/api-keys)

## Quick Start

### 1. Clone and Setup Backend

```bash
# Clone repository (if from git)
cd SvontAi

# Setup Python environment
cd backend
python -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

Create `backend/.env` file:

```env
# Database - Update with your PostgreSQL credentials
DATABASE_URL=postgresql+psycopg://postgres:password@localhost:5432/smartwa

# JWT - Generate a secure random key
JWT_SECRET_KEY=your-super-secret-key-minimum-32-characters
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=14

# OpenAI - Get from https://platform.openai.com/api-keys
OPENAI_API_KEY=sk-your-openai-api-key
OPENAI_MODEL=gpt-4o-mini

# WhatsApp Cloud API
WHATSAPP_BASE_URL=https://graph.facebook.com/v17.0

# URLs
BACKEND_URL=http://localhost:8000
FRONTEND_URL=http://localhost:3000

# Environment
ENVIRONMENT=dev
```

### 3. Setup Database

```bash
# Create PostgreSQL database
createdb smartwa

# Or using psql
psql -U postgres
CREATE DATABASE smartwa;
\q

# Run migrations
cd backend
alembic upgrade head
```

### 4. Start Backend Server

```bash
cd backend
uvicorn app.main:app --reload
```

The API will be available at:
- **API**: http://localhost:8000
- **Swagger Docs**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### 5. Setup Frontend

```bash
cd frontend

# Install dependencies
npm install

# Create environment file
echo "NEXT_PUBLIC_BACKEND_URL=http://localhost:8000" > .env.local

# Start development server
npm run dev
```

The dashboard will be available at:
- **Dashboard**: http://localhost:3000

## Testing the Setup

### 1. Create a User

Visit http://localhost:3000/register and create an account.

### 2. Create a Bot

After logging in:
1. Go to "Botlar" (Bots)
2. Click "Yeni Bot" (New Bot)
3. Fill in details and create

### 3. Add Knowledge

1. Click on your bot
2. Go to "Bilgi Tabanı" (Knowledge Base)
3. Add Q&A pairs

### 4. Test Widget

After creating a bot, copy the public key and test the widget:

```html
<!DOCTYPE html>
<html>
<head>
    <title>Widget Test</title>
</head>
<body>
    <h1>Widget Test Page</h1>
    <script
      src="http://localhost:8000/widget.js"
      data-bot-key="YOUR_BOT_PUBLIC_KEY"
      data-api-url="http://localhost:8000"
    ></script>
</body>
</html>
```

## WhatsApp Integration

SvontAi uses the official **Embedded Signup** flow for WhatsApp.

### Quick Setup

1. Go to `/dashboard/setup/whatsapp` in the dashboard
2. Click **"WhatsApp'ı Bağla"**
3. Complete Meta authorization in the popup

For detailed configuration (Meta App, webhook, env vars), see:
`docs/WHATSAPP_EMBEDDED_SIGNUP.md`

> Manual token entry is now considered legacy and only needed if Embedded Signup is unavailable.

## Common Issues

### Database Connection Error

```
sqlalchemy.exc.OperationalError: could not connect to server
```

**Solution**: Check PostgreSQL is running and credentials are correct.

### OpenAI API Error

```
openai.error.AuthenticationError: Incorrect API key
```

**Solution**: Verify your API key in `.env` file.

### CORS Error in Browser

**Solution**: Ensure `FRONTEND_URL` in backend `.env` matches your frontend URL.

### Migration Issues

```bash
# Reset migrations
alembic downgrade base
alembic upgrade head
```

## Production Deployment

### Backend (Railway)

1. Connect your GitHub repository
2. Add environment variables
3. Deploy

### Frontend (Vercel)

1. Import project from GitHub
2. Set `NEXT_PUBLIC_BACKEND_URL` to your backend URL
3. Deploy

### Widget Distribution

Host `widget/index.js` on a CDN or serve from your backend.

## Need Help?

- Check the logs: `uvicorn` and browser console
- API documentation: http://localhost:8000/docs
- Create an issue on GitHub
