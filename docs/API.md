# SvontAi API Documentation

Base URL: `http://localhost:8000`

## Authentication

All protected endpoints require a Bearer token in the Authorization header:

```
Authorization: Bearer <access_token>
```

---

## Auth Endpoints

### Register User

```http
POST /auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "securepassword",
  "full_name": "John Doe"
}
```

**Response 201:**
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "full_name": "John Doe",
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

### Login

```http
POST /auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "securepassword"
}
```

**Response 200:**
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer"
}
```

### Refresh Token

```http
POST /auth/refresh
Content-Type: application/json

{
  "refresh_token": "eyJ..."
}
```

**Response 200:**
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer"
}
```

---

## User Endpoints

### Get Current User

```http
GET /me
Authorization: Bearer <token>
```

**Response 200:**
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "full_name": "John Doe",
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z",
  "tenants": [...]
}
```

### Update Current User

```http
PUT /me
Authorization: Bearer <token>
Content-Type: application/json

{
  "full_name": "Jane Doe"
}
```

---

## Tenant Endpoints

### Create Tenant

```http
POST /tenants
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "My Business"
}
```

### Get My Tenants

```http
GET /tenants/my
Authorization: Bearer <token>
```

---

## Bot Endpoints

### List Bots

```http
GET /bots
Authorization: Bearer <token>
```

**Response 200:**
```json
[
  {
    "id": "uuid",
    "tenant_id": "uuid",
    "name": "Customer Support Bot",
    "description": "Handles customer inquiries",
    "welcome_message": "Merhaba! Size nasıl yardımcı olabilirim?",
    "language": "tr",
    "primary_color": "#3C82F6",
    "widget_position": "right",
    "public_key": "bot_xxx...",
    "is_active": true,
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-01T00:00:00Z"
  }
]
```

### Create Bot

```http
POST /bots
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "Support Bot",
  "description": "Customer support assistant",
  "welcome_message": "Merhaba!",
  "language": "tr",
  "primary_color": "#3C82F6",
  "widget_position": "right"
}
```

### Get Bot

```http
GET /bots/{bot_id}
Authorization: Bearer <token>
```

### Update Bot

```http
PUT /bots/{bot_id}
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "Updated Bot Name",
  "is_active": false
}
```

### Delete Bot

```http
DELETE /bots/{bot_id}
Authorization: Bearer <token>
```

---

## Knowledge Base Endpoints

### List Knowledge Items

```http
GET /bots/{bot_id}/knowledge
Authorization: Bearer <token>
```

**Response 200:**
```json
[
  {
    "id": "uuid",
    "bot_id": "uuid",
    "title": "Working Hours",
    "question": "What are your working hours?",
    "answer": "We are open Monday to Friday, 9 AM to 6 PM.",
    "created_at": "2024-01-01T00:00:00Z"
  }
]
```

### Create Knowledge Item

```http
POST /bots/{bot_id}/knowledge
Authorization: Bearer <token>
Content-Type: application/json

{
  "title": "Working Hours",
  "question": "What are your working hours?",
  "answer": "We are open Monday to Friday, 9 AM to 6 PM."
}
```

### Update Knowledge Item

```http
PUT /bots/{bot_id}/knowledge/{item_id}
Authorization: Bearer <token>
Content-Type: application/json

{
  "answer": "We are open Monday to Saturday, 9 AM to 8 PM."
}
```

### Delete Knowledge Item

```http
DELETE /bots/{bot_id}/knowledge/{item_id}
Authorization: Bearer <token>
```

---

## Conversation Endpoints

### List Bot Conversations

```http
GET /bots/{bot_id}/conversations?skip=0&limit=50
Authorization: Bearer <token>
```

**Response 200:**
```json
[
  {
    "id": "uuid",
    "bot_id": "uuid",
    "external_user_id": "web_xxx...",
    "source": "web_widget",
    "metadata": {},
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-01T00:00:00Z"
  }
]
```

### Get Conversation Messages

```http
GET /conversations/{conversation_id}/messages?skip=0&limit=100
Authorization: Bearer <token>
```

---

## Lead Endpoints

### List All Leads

```http
GET /leads?search=john&skip=0&limit=50
Authorization: Bearer <token>
```

### List Bot Leads

```http
GET /leads/bots/{bot_id}?skip=0&limit=50
Authorization: Bearer <token>
```

---

## Public Chat Endpoints (No Auth Required)

### Initialize Chat

```http
POST /public/chat/init
Content-Type: application/json

{
  "bot_public_key": "bot_xxx...",
  "external_user_id": null
}
```

**Response 200:**
```json
{
  "conversation_id": "uuid",
  "external_user_id": "web_xxx...",
  "bot": {
    "name": "Support Bot",
    "welcome_message": "Merhaba!",
    "primary_color": "#3C82F6",
    "widget_position": "right"
  },
  "welcome_message": "Merhaba!"
}
```

### Send Chat Message

```http
POST /public/chat/send
Content-Type: application/json

{
  "conversation_id": "uuid",
  "message": "What are your working hours?"
}
```

**Response 200:**
```json
{
  "message_id": "uuid",
  "reply": "We are open Monday to Friday, 9 AM to 6 PM."
}
```

### Create Public Lead

```http
POST /public/leads
Content-Type: application/json

{
  "bot_public_key": "bot_xxx...",
  "name": "John Doe",
  "email": "john@example.com",
  "phone": "+905551234567",
  "conversation_id": "uuid"
}
```

---

## WhatsApp Webhook Endpoints

### Verify Webhook (GET)

```http
GET /whatsapp/webhook?hub.mode=subscribe&hub.verify_token=xxx&hub.challenge=yyy
```

### Receive Messages (POST)

```http
POST /whatsapp/webhook
Content-Type: application/json

{
  "entry": [...]
}
```

---

## WhatsApp Integration Endpoints

### Create/Update Integration

```http
POST /bots/{bot_id}/whatsapp-integration
Authorization: Bearer <token>
Content-Type: application/json

{
  "whatsapp_phone_number_id": "123456789",
  "whatsapp_business_account_id": "987654321",
  "access_token": "EAAx...",
  "webhook_verify_token": "my_verify_token"
}
```

### Get Integration

```http
GET /bots/{bot_id}/whatsapp-integration
Authorization: Bearer <token>
```

---

## Error Responses

### 400 Bad Request

```json
{
  "detail": "Validation error message"
}
```

### 401 Unauthorized

```json
{
  "detail": "Token geçersiz veya süresi dolmuş"
}
```

### 404 Not Found

```json
{
  "detail": "Resource not found"
}
```

### 500 Internal Server Error

```json
{
  "detail": "Internal server error"
}
```

