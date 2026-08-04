from __future__ import annotations

import uuid
from types import SimpleNamespace
from uuid import UUID

from app.core.config import settings
from app.core.plans import PLAN_MONTHLY_TOOL_RUN_LIMITS
from app.models.subscription import TenantSubscription
from app.models.ticket import Ticket
from app.models.tool import Tool
from app.models.tool_run import ToolRun
from app.services.payment_service import CheckoutSessionResult, PaymentService
from app.services.tool_seed_service import seed_initial_tools


def _extract_6_digit_code(message: str) -> str:
    for token in (message or "").split():
        if token.isdigit() and len(token) == 6:
            return token
    raise AssertionError(f"Could not extract verification code from message: {message!r}")


def _register_and_login(client) -> tuple[str, str]:
    email = f"billing-{uuid.uuid4().hex[:10]}@example.com"
    password = "Password123!"

    register_resp = client.post(
        "/auth/register",
        json={"email": email, "password": password, "full_name": "Billing User", "terms_accepted": True, "privacy_notice_acknowledged": True, "terms_version": "2026-08-04", "privacy_version": "2026-08-04", "kvkk_notice_version": "2026-08-04"},
    )
    assert register_resp.status_code == 201, register_resp.text

    request_code = client.post("/auth/email-verification/request", json={"email": email})
    assert request_code.status_code == 200, request_code.text
    code = _extract_6_digit_code(request_code.json().get("message", ""))
    confirm_code = client.post("/auth/email-verification/confirm", json={"email": email, "code": code})
    assert confirm_code.status_code == 200, confirm_code.text

    login_resp = client.post("/auth/login", json={"email": email, "password": password})
    assert login_resp.status_code == 200, login_resp.text
    access_token = login_resp.json()["access_token"]

    tenant_resp = client.post(
        "/tenants",
        json={"name": "Billing Tenant"},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert tenant_resp.status_code == 201, tenant_resp.text
    tenant_id = tenant_resp.json()["id"]

    return access_token, tenant_id


def test_monthly_limit_enforced_for_tools_run(client):
    from app.db import session as session_module

    original_free_limit = PLAN_MONTHLY_TOOL_RUN_LIMITS["free"]
    PLAN_MONTHLY_TOOL_RUN_LIMITS["free"] = 1

    try:
        access_token, tenant_id = _register_and_login(client)
        headers = {"Authorization": f"Bearer {access_token}", "X-Tenant-ID": tenant_id}

        db = session_module.SessionLocal()
        try:
            seed_initial_tools(db)
            tool = db.query(Tool).filter(Tool.slug == "meeting_summary").one()
            tool.required_plan = "free"
            tool.is_premium = False
            db.add(
                ToolRun(
                    request_id="already-used-run",
                    tenant_id=UUID(tenant_id),
                    user_id=None,
                    tool_slug="meeting_summary",
                    status="success",
                    tool_input_json={},
                    output_json={"summary": "done"},
                    usage_json={},
                    artifacts_json=[],
                    context_json={},
                )
            )
            db.commit()
        finally:
            db.close()

        payload = {
            "requestId": "new-run-over-limit",
            "toolSlug": "meeting_summary",
            "toolInput": {"text": "Toplanti notlari"},
            "context": {"locale": "tr-TR", "timezone": "Europe/Istanbul", "channel": "web", "memory": {}},
        }
        response = client.post("/tools/run", json=payload, headers=headers)
        assert response.status_code == 402, response.text
        detail = response.json().get("detail", {})
        assert detail.get("code") == "PLAN_LIMIT_EXCEEDED"
    finally:
        PLAN_MONTHLY_TOOL_RUN_LIMITS["free"] = original_free_limit


def test_billing_checkout_session_returns_url(client, monkeypatch):
    access_token, tenant_id = _register_and_login(client)
    headers = {"Authorization": f"Bearer {access_token}", "X-Tenant-ID": tenant_id}

    def _fake_checkout(self, **kwargs):
        return CheckoutSessionResult(checkout_url="https://checkout.stripe.test/session", provider="stripe")

    monkeypatch.setattr(PaymentService, "create_checkout_session", _fake_checkout)
    response = client.post(
        "/billing/stripe/checkout-session",
        json={"plan": "pro", "interval": "monthly"},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json().get("url") == "https://checkout.stripe.test/session"


def test_manual_billing_config_and_plan_request_are_idempotent(client):
    from app.db import session as session_module

    previous_mode = settings.BILLING_MODE
    previous_payments_enabled = settings.PAYMENTS_ENABLED
    settings.BILLING_MODE = "manual"
    settings.PAYMENTS_ENABLED = False

    try:
        config_response = client.get("/billing/config")
        assert config_response.status_code == 200, config_response.text
        assert config_response.json()["mode"] == "manual"
        assert config_response.json()["payments_enabled"] is False

        access_token, tenant_id = _register_and_login(client)
        headers = {"Authorization": f"Bearer {access_token}", "X-Tenant-ID": tenant_id}
        payload = {"plan": "pro", "interval": "monthly"}

        direct_upgrade = client.post(
            "/subscription/upgrade",
            json={"plan_name": "pro", "interval": "monthly"},
            headers=headers,
        )
        assert direct_upgrade.status_code == 409, direct_upgrade.text

        first = client.post("/billing/manual-request", json=payload, headers=headers)
        assert first.status_code == 200, first.text
        assert first.json()["status"] == "pending"
        assert first.json()["duplicate"] is False

        second = client.post("/billing/manual-request", json=payload, headers=headers)
        assert second.status_code == 200, second.text
        assert second.json()["ticket_id"] == first.json()["ticket_id"]
        assert second.json()["duplicate"] is True

        db = session_module.SessionLocal()
        try:
            tickets = db.query(Ticket).filter(
                Ticket.tenant_id == tenant_id,
                Ticket.subject.like("Plan talebi:%"),
            ).all()
            assert len(tickets) == 1
        finally:
            db.close()
    finally:
        settings.BILLING_MODE = previous_mode
        settings.PAYMENTS_ENABLED = previous_payments_enabled


def test_billing_webhook_updates_subscription_and_is_idempotent(client, monkeypatch):
    from app.db import session as session_module

    previous_secret = settings.STRIPE_WEBHOOK_SECRET
    settings.STRIPE_WEBHOOK_SECRET = "whsec_test"

    try:
        _, tenant_id = _register_and_login(client)

        fake_event = SimpleNamespace(
            id="evt_checkout_completed_1",
            type="checkout.session.completed",
            data=SimpleNamespace(
                object=SimpleNamespace(
                    metadata={"tenant_id": tenant_id, "plan_name": "pro"},
                    client_reference_id=tenant_id,
                    customer="cus_123",
                    subscription="sub_123",
                )
            ),
            to_dict_recursive=lambda: {"id": "evt_checkout_completed_1", "type": "checkout.session.completed"},
        )

        from app.api.routers import billing as billing_router_module

        monkeypatch.setattr(
            billing_router_module,
            "stripe",
            SimpleNamespace(
                Webhook=SimpleNamespace(
                    construct_event=lambda payload, sig_header, secret: fake_event
                )
            ),
        )

        response = client.post(
            "/billing/stripe/webhook",
            data="{}",
            headers={"stripe-signature": "sig_test"},
        )
        assert response.status_code == 200, response.text
        assert response.json().get("received") is True

        db = session_module.SessionLocal()
        try:
            subscription = db.query(TenantSubscription).filter(TenantSubscription.tenant_id == UUID(tenant_id)).first()
            assert subscription is not None
            assert subscription.plan.name == "pro"
            assert subscription.external_customer_id == "cus_123"
            assert subscription.external_subscription_id == "sub_123"
        finally:
            db.close()

        duplicate = client.post(
            "/billing/stripe/webhook",
            data="{}",
            headers={"stripe-signature": "sig_test"},
        )
        assert duplicate.status_code == 200, duplicate.text
        assert duplicate.json().get("duplicate") is True
    finally:
        settings.STRIPE_WEBHOOK_SECRET = previous_secret
