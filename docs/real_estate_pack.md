# SvontAI Real Estate Pack (MVP)

## Amaç
Real Estate Pack, mevcut SvontAI Tool Engine’in üzerine modüler bir sektör katmanı ekler:
- WhatsApp lead karşılama + segmentasyon
- Kriter bazlı ilan eşleştirme
- Follow-up recovery otomasyonu
- Randevu planlama (manuel + Google Calendar entegrasyon iskeleti)
- Template registry ve haftalık metrik raporu

Bu katman tenant bazlı açılıp/kapanır, mevcut bot/n8n akışını bozmaz.

## Mimari (metin diyagram)
1. `POST /whatsapp/webhook` inbound mesajı alır.
   - Uyumluluk için `POST /webhooks/whatsapp` alias endpoint’i de desteklenir.
2. `whatsapp_webhook.handle_incoming_message`:
   - Mesajı `messages` tablosuna yazar.
   - Tenant’ta Real Estate Pack aktifse `RealEstateService.handle_inbound_whatsapp_message` çağrılır.
   - State machine sonucu yanıt üretirse WhatsApp Cloud API’ye text gönderilir.
   - Pack devreye girmediyse mevcut n8n/legacy akış çalışır.
3. Real Estate state verisi `real_estate_conversation_states` tablosunda tutulur.
4. Eşleşen ilanlar `real_estate_listings` üzerinden hesaplanır, olaylar `real_estate_lead_listing_events`’e yazılır.
5. Follow-up cron/manual tetikleyici `POST /real-estate/followups/run` ile `real_estate_followup_jobs` kuyruğunu işler.
6. Haftalık metrikler `real_estate_weekly_reports` tablosuna materialize edilir.

## Veri Modeli (MVP)
Eklenen tablolar:
- `real_estate_pack_settings`
- `real_estate_google_calendar_integrations`
- `real_estate_listings`
- `real_estate_conversation_states`
- `real_estate_lead_listing_events`
- `real_estate_appointments`
- `real_estate_followup_jobs`
- `real_estate_template_registry`
- `real_estate_weekly_reports`

Ek alan:
- `messages.external_id`

## State Machine (MVP)
Durumlar:
- `welcome`
- `qualify`
- `match_listings`
- `appointment`
- `followup`
- `handoff_agent`

Niyet:
- `buyer`
- `seller`
- `unknown`

Guardrails:
- Opt-out (`durdur/stop`) algılanırsa takip durdurulur.
- Uydurma ilan üretilmez; öneriler sadece `real_estate_listings` kaynağından gelir.
- PII snapshot (`name/phone`) state içinde encrypted tutulur.

## API Endpoints (MVP)
Tenant panel:
- `GET /real-estate/settings`
- `PUT /real-estate/settings`
- `GET /real-estate/listings`
- `POST /real-estate/listings`
- `PATCH /real-estate/listings/{listing_id}`
- `DELETE /real-estate/listings/{listing_id}`
- `POST /real-estate/listings/import/csv`
- `GET /real-estate/templates`
- `POST /real-estate/templates`
- `PATCH /real-estate/templates/{template_id}`
- `POST /real-estate/leads/{lead_id}/suggest-listings`
- `POST /real-estate/appointments/book`
- `POST /real-estate/followups/run`
- `GET /real-estate/analytics/weekly`
- `GET /real-estate/agents`
- `GET /real-estate/calendar/google/start`
- `GET /real-estate/calendar/google/callback`
- `GET /real-estate/calendar/google/status`
- `DELETE /real-estate/calendar/google/disconnect`
- `POST /real-estate/pdf/generate`
- `POST /real-estate/pdf/download`
- `POST /real-estate/leads/{lead_id}/listing-events`
- `GET /real-estate/leads/{lead_id}/ai-suggested-listings`
- `POST /real-estate/leads/{lead_id}/seller-service-report`
- `POST /real-estate/reports/weekly/send`

Super admin:
- `GET /admin/tenants/{tenant_id}/real-estate-pack`
- `PUT /admin/tenants/{tenant_id}/real-estate-pack`

Webhook alias:
- `GET /webhooks/whatsapp`
- `POST /webhooks/whatsapp`

## Frontend (MVP)
- Tool Catalog’a `Real Estate Pack` eklendi (`tool-real-estate-pack`).
- `Tool Workspace` içinde Real Estate Pack sekmesi:
  - Pack ayarları (persona, limitler)
  - Manual listing + CSV import
  - Template registry
  - Haftalık metrik ve follow-up tetikleme

## Ankara Pilot Senaryosu (kısa)
Buyer flow (8 adım):
1. “Merhaba ev bakıyorum”
2. Buyer intent + satılık/kiralık sorusu
3. Mülk tipi
4. Lokasyon
5. Bütçe
6. Oda/m²
7. İlk 3 ilan önerisi
8. Randevu isteği

Seller flow (10 adım):
1. “Evimi satmak istiyorum”
2. Satıcı intent doğrulama
3. Lokasyon
4. Mülk tipi
5. m²
6. Oda
7. Bina yaşı/tapu notu (manuel akış)
8. Fiyat beklentisi
9. Aciliyet
10. Danışmana özet/handoff

Follow-up simülasyonu:
- 1 saat sonra nazik ping
- Uygunsa ikinci dokunuş (ayar bazlı)

## Template Taslakları (10)
1. `re_welcome_buyer`
2. `re_welcome_seller`
3. `re_qualification_ping_1h`
4. `re_followup_recovery_1`
5. `re_followup_recovery_2`
6. `re_appointment_confirmation`
7. `re_appointment_reminder_1h`
8. `re_listing_suggestions`
9. `re_seller_intake_summary`
10. `re_optout_ack`

> Not: Bu sürümde registry’ye taslak olarak eklenir; Meta tarafında approved template id eşlemesi tenant tarafından yapılır.

## Scheduler (MVP)
- `REAL_ESTATE_AUTOMATION_ENABLED=true` olduğunda backend döngüsü:
  - periyodik follow-up çalıştırır,
  - satıcı servis raporlarını otomatik gönderir,
  - haftalık e-posta + PDF raporunu planlı pencerede yollar.
