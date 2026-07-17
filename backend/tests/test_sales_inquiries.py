from app.models.sales_inquiry import SalesInquiry


def _payload(email: str = "owner@example.com") -> dict:
    return {
        "name": "Test İşletme Sahibi",
        "email": email,
        "company": "Test Marka",
        "phone": "+905551112233",
        "plan": "pro",
        "interval": "monthly",
        "message": "WhatsApp otomasyonu için görüşmek istiyorum.",
        "website": "",
    }


def test_public_contact_persists_and_deduplicates(client):
    from app.db import session as session_module

    first = client.post("/public/contact", json=_payload())
    assert first.status_code == 202, first.text
    assert first.json()["accepted"] is True
    assert first.json()["duplicate"] is False
    inquiry_id = first.json()["inquiry_id"]

    second = client.post("/public/contact", json=_payload())
    assert second.status_code == 202, second.text
    assert second.json()["duplicate"] is True
    assert second.json()["inquiry_id"] == inquiry_id

    db = session_module.SessionLocal()
    try:
        rows = db.query(SalesInquiry).all()
        assert len(rows) == 1
        assert rows[0].email == "owner@example.com"
        assert rows[0].email_delivered is False
    finally:
        db.close()


def test_public_contact_honeypot_is_not_persisted(client):
    from app.db import session as session_module

    payload = _payload("bot@example.com")
    payload["website"] = "https://spam.example"
    response = client.post("/public/contact", json=payload)
    assert response.status_code == 202, response.text
    assert response.json()["inquiry_id"] is None

    db = session_module.SessionLocal()
    try:
        assert db.query(SalesInquiry).count() == 0
    finally:
        db.close()
