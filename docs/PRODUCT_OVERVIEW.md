# SvontAi - Ürün Genel Bakış

## 🎯 Vizyon

SvontAi, işletmelerin WhatsApp ve web üzerinden 7/24 otomatik müşteri desteği sağlamasına olanak tanıyan bir AI asistan platformudur.

## 🏗️ Mimari

### Backend (FastAPI)
- **API Layer**: RESTful API endpoints
- **Service Layer**: Business logic (AI, Lead Detection, Analytics)
- **Data Layer**: SQLAlchemy ORM + PostgreSQL/SQLite
- **Authentication**: JWT-based auth with refresh tokens

### Frontend (Next.js 14)
- **App Router**: Modern Next.js routing
- **State Management**: Zustand + React Query
- **UI Components**: shadcn/ui + Tailwind CSS
- **Real-time**: WebSocket support (planned)

### Widget
- **Standalone JS**: Embeddable chat widget
- **Lightweight**: No dependencies
- **Customizable**: Colors, position, welcome message

## 📦 Core Features

### 1. Multi-tenant Architecture
- Her müşteri izole bir tenant
- Tenant başına bot, lead, conversation
- Plan bazlı limit kontrolü

### 2. AI Chat Bot
- OpenAI GPT-4 entegrasyonu
- Knowledge base ile context injection
- Guardrails ve safety features
- Tone ve emoji konfigürasyonu

### 3. WhatsApp Integration
- Meta Cloud API
- Embedded Signup (OAuth)
- Webhook handling
- Template messages (planned)

### 4. Lead Automation
- Otomatik contact detection (email, phone, name)
- Lead scoring
- Conversation tagging

### 5. Operator Takeover
- AI duraklatma
- Manuel müdahale
- Conversation status tracking

### 6. Analytics
- Daily/weekly/monthly stats
- Bot performance metrics
- Source breakdown (WhatsApp vs Widget)

## 🔐 Güvenlik

- JWT authentication
- Fernet encryption for tokens
- Webhook signature validation
- Rate limiting
- CORS protection

## 💰 Monetization

### Plans
| Plan | Fiyat | Mesaj Limiti | Bot Limiti |
|------|-------|--------------|------------|
| Free | ₺0 | 100/ay | 1 |
| Starter | ₺299/ay | 1000/ay | 2 |
| Pro | ₺599/ay | 5000/ay | 5 |
| Business | ₺1299/ay | 20000/ay | 20 |

### Feature Flags
- `whatsapp_integration`: WhatsApp bağlantısı
- `analytics`: Detaylı analitikler
- `operator_takeover`: Manuel müdahale
- `lead_automation`: Otomatik lead yakalama
- `api_access`: API erişimi
- `custom_branding`: Özel markalama

## 🚀 Future Roadmap

### Phase 1 (Current)
- ✅ Core chat functionality
- ✅ Knowledge base
- ✅ Lead management
- ✅ Basic analytics
- ✅ Subscription system

### Phase 2
- [ ] Payment integration (Stripe/Iyzico)
- [ ] WhatsApp template messages
- [ ] Advanced AI training
- [ ] Team collaboration

### Phase 3
- [ ] Multi-language support
- [ ] Voice messages
- [ ] CRM integrations
- [ ] White-label solution

## 📊 Database Schema

```
Users
├── Tenants (1:N)
│   ├── Bots (1:N)
│   │   ├── Knowledge Items (1:N)
│   │   ├── Conversations (1:N)
│   │   │   ├── Messages (1:N)
│   │   │   └── Lead (1:1)
│   │   └── Bot Settings (1:1)
│   ├── Subscription (1:1)
│   ├── Onboarding (1:1)
│   └── WhatsApp Accounts (1:N)
└── Plans (Reference)
```

## 🔧 Environment Variables

```env
# Required
DATABASE_URL=postgresql://...
JWT_SECRET_KEY=...
OPENAI_API_KEY=...

# WhatsApp
META_APP_ID=...
META_APP_SECRET=...

# Optional
REDIS_URL=redis://...
ENCRYPTION_KEY=...
```

## 📞 Support

- Documentation: `/docs`
- Help Center: `/dashboard/help`
- Email: support@svontai.com

