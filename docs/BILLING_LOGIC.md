# SvontAi - Faturalandırma Mantığı

## 💳 Plan Sistemi

### Plan Tiers

| Plan | Aylık | Yıllık | Mesaj | Bot | Knowledge |
|------|-------|--------|-------|-----|-----------|
| Free | ₺0 | ₺0 | 100 | 1 | 20 |
| Starter | ₺299 | ₺2,990 | 1,000 | 2 | 100 |
| Pro | ₺599 | ₺5,990 | 5,000 | 5 | 500 |
| Business | ₺1,299 | ₺12,990 | 20,000 | 20 | 2,000 |

### Feature Flags

```python
FEATURE_FLAGS = {
    "free": {
        "whatsapp_integration": False,
        "analytics": False,
        "custom_branding": False,
        "priority_support": False,
        "api_access": False,
        "export_data": False,
        "operator_takeover": False,
        "lead_automation": False
    },
    "starter": {
        "whatsapp_integration": True,
        "analytics": True,
        "export_data": True,
        "lead_automation": True
    },
    "pro": {
        "whatsapp_integration": True,
        "analytics": True,
        "custom_branding": True,
        "priority_support": True,
        "api_access": True,
        "export_data": True,
        "operator_takeover": True,
        "lead_automation": True
    },
    "business": {
        # All pro features +
        "white_label": True,
        "dedicated_support": True
    }
}
```

## 📊 Subscription States

```python
class SubscriptionStatus(Enum):
    TRIAL = "trial"        # 14-day free trial
    ACTIVE = "active"      # Paid and active
    PAST_DUE = "past_due"  # Payment failed
    CANCELLED = "cancelled" # User cancelled
    EXPIRED = "expired"    # Trial/subscription ended
```

### State Transitions

```
[New User] → TRIAL (14 days)
     ↓
TRIAL → ACTIVE (payment success)
     ↓
TRIAL → EXPIRED (no payment after 14 days)

ACTIVE → PAST_DUE (payment failed)
     ↓
PAST_DUE → ACTIVE (payment retry success)
     ↓
PAST_DUE → CANCELLED (3 failed attempts)

ACTIVE → CANCELLED (user request)
```

## 🔢 Usage Tracking

### Message Counting

```python
def increment_message_count(tenant_id):
    subscription = get_subscription(tenant_id)
    subscription.messages_used_this_month += 1
    
    # Check if limit reached
    if subscription.messages_used_this_month >= subscription.plan.message_limit:
        # Soft block - don't send AI responses
        return False
    return True
```

### Monthly Reset

```python
def reset_monthly_usage():
    """Run as cron job on 1st of each month"""
    subscriptions = get_all_active_subscriptions()
    for sub in subscriptions:
        sub.messages_used_this_month = 0
        sub.usage_reset_at = datetime.utcnow()
```

## 🚫 Limit Enforcement

### Message Limit

```python
def check_message_limit(tenant_id):
    subscription = get_subscription(tenant_id)
    
    if not subscription.is_active():
        return False, "Abonelik aktif değil"
    
    if subscription.messages_used >= subscription.plan.message_limit:
        return False, f"Limit aşıldı ({subscription.plan.message_limit}/ay)"
    
    return True, "OK"
```

### Bot Limit

```python
def check_bot_limit(tenant_id, current_count):
    subscription = get_subscription(tenant_id)
    
    if current_count >= subscription.plan.bot_limit:
        return False, f"Bot limiti: {subscription.plan.bot_limit}"
    
    return True, "OK"
```

### Feature Check

```python
def check_feature(tenant_id, feature_key):
    subscription = get_subscription(tenant_id)
    return subscription.plan.feature_flags.get(feature_key, False)
```

## 💰 Payment Integration (TODO)

### Stripe Integration

```python
# Future implementation
def create_checkout_session(tenant_id, plan_name):
    """
    1. Create Stripe checkout session
    2. Return checkout URL
    3. Handle success/cancel webhooks
    """
    pass

def handle_stripe_webhook(event):
    """
    Events to handle:
    - checkout.session.completed → Upgrade plan
    - invoice.paid → Continue subscription
    - invoice.payment_failed → Mark as PAST_DUE
    - customer.subscription.deleted → Cancel
    """
    pass
```

### Iyzico Integration (Turkey)

```python
# For Turkish market
def create_iyzico_payment(tenant_id, plan_name):
    """
    1. Create payment form
    2. Handle 3D Secure
    3. Process callback
    """
    pass
```

## 📈 Upgrade/Downgrade

### Upgrade

```python
def upgrade_plan(tenant_id, new_plan_name):
    # 1. Validate plan exists
    # 2. Calculate prorated amount (for paid upgrades)
    # 3. Update subscription
    # 4. Apply new limits immediately
    
    subscription.plan_id = new_plan.id
    subscription.status = "active"
    subscription.current_period_start = now()
    subscription.current_period_end = now() + 30 days
```

### Downgrade

```python
def downgrade_plan(tenant_id, new_plan_name):
    # 1. Check current usage vs new limits
    # 2. Warn if over limits
    # 3. Apply at end of current period
    
    subscription.plan_id = new_plan.id  # Effective at period end
    subscription.scheduled_change = new_plan_name
```

## 🎁 Trial Management

### Trial Creation

```python
def create_trial(tenant_id, plan_name="starter"):
    now = datetime.utcnow()
    
    subscription = TenantSubscription(
        tenant_id=tenant_id,
        plan_id=get_plan(plan_name).id,
        status="trial",
        started_at=now,
        trial_ends_at=now + timedelta(days=14)
    )
```

### Trial Expiration

```python
def check_trial_expiration():
    """Run as daily cron job"""
    expired_trials = get_trials_ending_before(datetime.utcnow())
    
    for sub in expired_trials:
        if no_payment_method(sub.tenant_id):
            # Downgrade to free
            sub.plan_id = get_plan("free").id
            sub.status = "active"
        else:
            # Start paid subscription
            charge_subscription(sub)
```

## 📊 Usage Analytics

### Daily Stats

```python
def get_usage_stats(tenant_id):
    subscription = get_subscription(tenant_id)
    
    return {
        "plan_name": subscription.plan.display_name,
        "messages_used": subscription.messages_used_this_month,
        "message_limit": subscription.plan.message_limit,
        "messages_remaining": max(0, limit - used),
        "usage_percent": (used / limit) * 100,
        "days_until_reset": days_until_first_of_month()
    }
```

## 🔐 Security

### Payment Token Storage

```python
# Never store raw card data
# Use payment provider's token system
class PaymentMethod:
    provider: str  # "stripe", "iyzico"
    external_id: str  # Provider's token
    last_four: str  # For display only
```

### Webhook Verification

```python
def verify_stripe_webhook(payload, signature):
    endpoint_secret = settings.STRIPE_WEBHOOK_SECRET
    return stripe.Webhook.construct_event(
        payload, signature, endpoint_secret
    )
```

## 📋 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/subscription/plans` | List all plans |
| GET | `/subscription/current` | Get current subscription |
| GET | `/subscription/usage` | Get usage stats |
| POST | `/subscription/upgrade` | Upgrade plan |
| POST | `/subscription/cancel` | Cancel subscription |
| GET | `/subscription/check-feature/{key}` | Check feature access |

## 🎯 Billing Events (Future)

```python
# Events to track
BILLING_EVENTS = [
    "subscription.created",
    "subscription.upgraded",
    "subscription.downgraded",
    "subscription.cancelled",
    "payment.succeeded",
    "payment.failed",
    "trial.started",
    "trial.ended",
    "limit.reached"
]
```

