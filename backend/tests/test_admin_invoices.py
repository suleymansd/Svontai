from __future__ import annotations

import uuid

from app.core.security import get_password_hash
from app.models.onboarding import AuditLog
from app.models.user import User


def _login_user(client, *, is_admin: bool) -> str:
    from app.db import session as session_module

    email = f"invoice-{'admin' if is_admin else 'user'}-{uuid.uuid4().hex[:10]}@example.com"
    password = "Password123!"
    db = session_module.SessionLocal()
    try:
        db.add(User(
            email=email,
            full_name="Invoice Test User",
            password_hash=get_password_hash(password),
            is_admin=is_admin,
            is_active=True,
            email_verified=True,
        ))
        db.commit()
    finally:
        db.close()

    payload = {"email": email, "password": password}
    if is_admin:
        payload.update({"portal": "super_admin", "admin_session_note": "invoice test"})
    response = client.post("/auth/login", json=payload)
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _invoice_payload() -> dict:
    return {
        "issue_date": "2026-07-21",
        "due_date": "2026-07-28",
        "currency": "TRY",
        "seller_name": "SvontAI",
        "seller_email": "info@aparial.com",
        "seller_address": "İstanbul",
        "customer_name": "Örnek İşletme",
        "customer_email": "musteri@example.com",
        "customer_address": "Ankara",
        "items": [
            {"description": "SvontAI aylık hizmet", "quantity": "2", "unit": "ay", "unit_price": "100", "tax_rate": "20"},
            {"description": "Kurulum", "quantity": "1", "unit": "adet", "unit_price": "50", "tax_rate": "10"},
        ],
        "notes": "Ödeme banka havalesi ile alınacaktır.",
    }


def test_invoice_endpoints_are_super_admin_only(client):
    token = _login_user(client, is_admin=False)
    response = client.post(
        "/admin/invoices",
        json=_invoice_payload(),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403, response.text


def test_admin_can_create_list_and_update_proforma(client):
    from app.db import session as session_module

    token = _login_user(client, is_admin=True)
    headers = {"Authorization": f"Bearer {token}"}
    create = client.post("/admin/invoices", json=_invoice_payload(), headers=headers)
    assert create.status_code == 201, create.text
    invoice = create.json()
    assert invoice["invoice_number"].startswith("SV-20260721-")
    assert invoice["document_type"] == "proforma"
    assert invoice["status"] == "draft"
    assert invoice["subtotal"] == "250.00"
    assert invoice["tax_total"] == "45.00"
    assert invoice["total"] == "295.00"
    assert "e-Fatura" in invoice["legal_notice"]

    listing = client.get("/admin/invoices?search=Örnek", headers=headers)
    assert listing.status_code == 200, listing.text
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["id"] == invoice["id"]

    detail = client.get(f"/admin/invoices/{invoice['id']}", headers=headers)
    assert detail.status_code == 200, detail.text

    updated = client.patch(
        f"/admin/invoices/{invoice['id']}/status",
        json={"status": "sent"},
        headers=headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["status"] == "sent"

    db = session_module.SessionLocal()
    try:
        actions = {
            row.action
            for row in db.query(AuditLog).filter(AuditLog.resource_id == invoice["id"]).all()
        }
        assert {"admin.invoice.create", "admin.invoice.status_update"} <= actions
    finally:
        db.close()


def test_invoice_rejects_invalid_due_date(client):
    token = _login_user(client, is_admin=True)
    payload = _invoice_payload()
    payload["due_date"] = "2026-07-20"
    response = client.post(
        "/admin/invoices",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422, response.text
