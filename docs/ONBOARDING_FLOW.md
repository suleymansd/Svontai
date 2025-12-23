# SvontAi - Onboarding Akışı

## 📋 Onboarding Adımları

### 1. İşletme Oluştur (create_tenant)
**Otomatik tamamlanır** - Kayıt sırasında tenant oluşturulur.

```python
# Tetikleyici: Kullanıcı kaydı
# Auto-complete: Tenant oluşturulduğunda
```

### 2. İlk Bot Oluştur (create_bot)
**Kullanıcı aksiyonu gerekli**

Kullanıcı:
- Bot adı girer
- Açıklama ekler (opsiyonel)
- Dil seçer (varsayılan: Türkçe)

```python
# Tetikleyici: POST /bots
# Complete condition: Bot count > 0
```

### 3. Karşılama Mesajı Ekle (add_welcome_message)
**Kullanıcı aksiyonu gerekli**

Kullanıcı:
- Default "Merhaba!" mesajını özelleştirir
- Botun ilk tepkisini belirler

```python
# Tetikleyici: PUT /bots/{id}
# Complete condition: welcome_message != default
```

### 4. Bilgi Tabanı Oluştur (add_knowledge)
**Kullanıcı aksiyonu gerekli**

Kullanıcı:
- En az 1 soru-cevap çifti ekler
- AI'ın bilgi kaynağını oluşturur

```python
# Tetikleyici: POST /bots/{id}/knowledge
# Complete condition: Knowledge count > 0
```

### 5. WhatsApp Bağla (connect_whatsapp)
**Opsiyonel**

Kullanıcı:
- Meta Business hesabı bağlar
- OAuth flow tamamlar
- Telefon numarası seçer

```python
# Tetikleyici: WhatsApp Embedded Signup completion
# Complete condition: WhatsApp account active
# Skip allowed: true
```

### 6. Bot Aktifleştir (activate_bot)
**Kullanıcı aksiyonu gerekli**

Kullanıcı:
- Botu aktif eder
- Yayına alır

```python
# Tetikleyici: PUT /bots/{id} { is_active: true }
# Complete condition: Bot is_active = true
```

## 🔄 Otomatik Progress Check

Her kritik API çağrısından sonra onboarding durumu kontrol edilir:

```typescript
// Frontend: useEffect ile check
await setupOnboardingApi.checkProgress()
```

```python
# Backend: Service method
def auto_check_progress(self, tenant_id):
    # Check each step's completion condition
    # Update steps accordingly
```

## 📊 Progress Tracking

### Percentage Calculation
```python
completed_required = count(step.completed for step in required_steps)
total_required = count(required_steps)
percentage = (completed_required / total_required) * 100
```

### Step Status
```python
class StepStatus:
    PENDING = "pending"
    COMPLETED = "completed"
    SKIPPED = "skipped"  # For optional steps
```

## 🎯 UI Components

### Onboarding Banner (Layout)
- Sidebar'da görünür
- Progress bar gösterir
- Tıklanınca wizard'a yönlendirir

### Onboarding Wizard Page
- Step-by-step görünüm
- Her adım için:
  - Status indicator (completed/current/locked)
  - Description
  - Action button
- Dismiss option

### Next Action CTA
Dashboard'da:
```typescript
const { action, message, url } = await setupOnboardingApi.getNextAction()
// Display: "Sonraki: {message}" with link to {url}
```

## 📝 Database Schema

```sql
CREATE TABLE tenant_onboarding (
    id UUID PRIMARY KEY,
    tenant_id UUID UNIQUE REFERENCES tenants(id),
    is_completed BOOLEAN DEFAULT FALSE,
    completed_at TIMESTAMP,
    steps JSONB DEFAULT '{}',
    current_step VARCHAR(50),
    dismissed BOOLEAN DEFAULT FALSE,
    dismissed_at TIMESTAMP
);
```

### Steps JSON Structure
```json
{
    "create_tenant": {
        "completed": true,
        "completed_at": "2024-01-15T12:00:00Z",
        "title": "İşletme Oluştur",
        "description": "İşletmenizi kaydedin",
        "order": 1,
        "required": true
    },
    ...
}
```

## 🔧 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/onboarding/setup/status` | Get current status |
| POST | `/onboarding/setup/complete-step` | Mark step complete |
| POST | `/onboarding/setup/dismiss` | Dismiss wizard |
| POST | `/onboarding/setup/check-progress` | Auto-check all steps |
| GET | `/onboarding/setup/next-action` | Get next recommended action |

## 🎨 UX Best Practices

1. **Non-blocking**: Onboarding optional ama görünür
2. **Progressive disclosure**: Sadece şu anki adım vurgulu
3. **Quick wins**: İlk adımlar kolay
4. **Value early**: Bot hemen test edilebilir
5. **Dismiss option**: Her zaman atlanabilir

## 📈 Success Metrics

- Completion rate: % of users completing all steps
- Time to first bot: Minutes from signup to active bot
- Engagement: Users returning after onboarding
- Feature adoption: % using each feature

