# SvontAi - WhatsApp Entegrasyon Akışı

## 🔄 Embedded Signup Flow

### 1. Kullanıcı Başlatır
```
[Dashboard] → "WhatsApp Bağla" butonuna tıklar
```

### 2. OAuth Redirect
```python
# Backend: /api/onboarding/whatsapp/start
def start_whatsapp_signup():
    state = generate_secure_state(tenant_id)
    
    oauth_url = f"https://www.facebook.com/{GRAPH_API_VERSION}/dialog/oauth?" + urlencode({
        "client_id": META_APP_ID,
        "redirect_uri": META_REDIRECT_URI,
        "scope": "whatsapp_business_management,whatsapp_business_messaging",
        "response_type": "code",
        "state": state
    })
    
    return {"oauth_url": oauth_url}
```

### 3. Meta'da Yetkilendirme
```
- Kullanıcı Facebook'a giriş yapar
- WhatsApp Business Account seçer
- Telefon numarası seçer
- İzinleri kabul eder
```

### 4. Callback Handling
```python
# Backend: /api/onboarding/whatsapp/callback
def handle_callback(code, state):
    # 1. Verify state
    tenant_id = verify_state(state)
    
    # 2. Exchange code for token
    token_response = exchange_code_for_token(code)
    access_token = token_response["access_token"]
    
    # 3. Get WABA ID
    waba_info = get_waba_info(access_token)
    
    # 4. Get Phone Number ID
    phone_info = get_phone_number_info(access_token, waba_info["id"])
    
    # 5. Subscribe to webhooks
    subscribe_to_webhooks(access_token, waba_info["id"])
    
    # 6. Save encrypted credentials
    save_whatsapp_account(tenant_id, {
        "waba_id": waba_info["id"],
        "phone_number_id": phone_info["id"],
        "display_phone": phone_info["display_phone_number"],
        "access_token": encrypt(access_token)
    })
```

## 📨 Webhook Message Flow

### Incoming Message
```
Meta Servers → POST /webhooks/whatsapp
    ↓
Verify signature
    ↓
Parse message
    ↓
Find bot by phone_number_id
    ↓
Get/Create conversation
    ↓
Check operator takeover
    ↓
If AI active:
    Generate AI response
    ↓
Send reply via API
    ↓
Log message
```

### Webhook Handler
```python
@router.post("/webhooks/whatsapp")
async def handle_webhook(request: Request):
    # 1. Verify signature
    signature = request.headers.get("X-Hub-Signature-256")
    if not verify_signature(await request.body(), signature):
        raise HTTPException(403, "Invalid signature")
    
    # 2. Parse payload
    payload = await request.json()
    
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            if change["field"] == "messages":
                await process_message(change["value"])
    
    return {"status": "ok"}
```

### Message Processing
```python
async def process_message(value):
    phone_number_id = value["metadata"]["phone_number_id"]
    
    for message in value.get("messages", []):
        # Find account
        account = get_account_by_phone_id(phone_number_id)
        
        # Find bot
        bot = get_bot_by_tenant(account.tenant_id)
        
        # Get/Create conversation
        conversation = get_or_create_conversation(
            bot_id=bot.id,
            external_user_id=message["from"],
            source="whatsapp"
        )
        
        # Save incoming message
        save_message(conversation.id, "user", message["text"]["body"])
        
        # Check if AI should respond
        if not conversation.is_ai_paused:
            # Generate response
            response = await ai_service.generate_reply(
                bot, knowledge_items, conversation, message["text"]["body"]
            )
            
            # Send response
            await send_whatsapp_message(
                phone_number_id,
                message["from"],
                response,
                account.access_token
            )
            
            # Save bot message
            save_message(conversation.id, "bot", response)
```

## 📤 Sending Messages

### Text Message
```python
async def send_whatsapp_message(phone_number_id, to, text, access_token):
    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{phone_number_id}/messages"
    
    response = await httpx.post(url, 
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": text}
        }
    )
    
    return response.json()
```

### Template Message (Future)
```python
async def send_template_message(phone_number_id, to, template_name, components, access_token):
    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{phone_number_id}/messages"
    
    response = await httpx.post(url,
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "messaging_product": "whatsapp",
            "to": to,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": "tr"},
                "components": components
            }
        }
    )
    
    return response.json()
```

## ⏰ 24-Hour Window Rule

### Rule
```
WhatsApp'ta kullanıcıya mesaj göndermek için:
- Kullanıcı son 24 saat içinde mesaj göndermiş olmalı
- VEYA onaylanmış template message kullanılmalı

Bu pencere dışında free-form mesaj gönderilemez.
```

### Implementation
```python
def can_send_freeform(conversation):
    if not conversation.messages:
        return False
    
    last_user_message = get_last_user_message(conversation)
    if not last_user_message:
        return False
    
    time_diff = datetime.utcnow() - last_user_message.created_at
    return time_diff < timedelta(hours=24)
```

## 🔐 Token Management

### Token Storage
```python
# Always encrypt tokens before storage
from app.core.encryption import encrypt, decrypt

def save_access_token(account_id, token):
    encrypted = encrypt(token)
    update_account(account_id, access_token=encrypted)

def get_access_token(account_id):
    account = get_account(account_id)
    return decrypt(account.access_token)
```

### Token Refresh (Long-lived)
```python
async def exchange_for_long_lived_token(short_token):
    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/oauth/access_token"
    
    response = await httpx.get(url, params={
        "grant_type": "fb_exchange_token",
        "client_id": META_APP_ID,
        "client_secret": META_APP_SECRET,
        "fb_exchange_token": short_token
    })
    
    data = response.json()
    return data["access_token"]  # Valid for ~60 days
```

## 📊 Status Tracking

### Onboarding Steps
```python
WHATSAPP_ONBOARDING_STEPS = [
    "oauth_started",      # User clicked connect
    "oauth_completed",    # Callback received
    "token_obtained",     # Access token saved
    "waba_linked",        # WABA ID obtained
    "phone_verified",     # Phone number verified
    "webhook_active",     # Webhook subscription active
    "ready"               # Fully operational
]
```

### Status API
```python
@router.get("/api/onboarding/whatsapp/status")
def get_status(tenant_id):
    account = get_whatsapp_account(tenant_id)
    
    return {
        "connected": account is not None,
        "status": account.status if account else "not_started",
        "phone_number": account.display_phone if account else None,
        "webhook_active": account.webhook_status == "active" if account else False
    }
```

## 🛠️ Troubleshooting

### Common Issues

1. **"Invalid OAuth Redirect URI"**
   - Check META_REDIRECT_URI in .env
   - Must match exactly in Meta App settings

2. **"Webhook verification failed"**
   - Check WEBHOOK_VERIFY_TOKEN
   - Ensure endpoint is publicly accessible (use ngrok for dev)

3. **"Messages not being received"**
   - Verify webhook subscription is active
   - Check webhook URL in Meta dashboard

4. **"Cannot send message"**
   - Check 24-hour window
   - Verify phone number format (+90...)
   - Check access token validity

## 📋 Required Meta App Permissions

```
- whatsapp_business_management (Manage WABA)
- whatsapp_business_messaging (Send/receive messages)
```

## 🔧 Environment Variables

```env
META_APP_ID=your_app_id
META_APP_SECRET=your_app_secret
META_REDIRECT_URI=https://your-domain.com/api/onboarding/whatsapp/callback
META_CONFIG_ID=optional_config_id
GRAPH_API_VERSION=v18.0
WEBHOOK_PUBLIC_URL=https://your-domain.com
WEBHOOK_VERIFY_TOKEN=your_random_verify_token
```

