from __future__ import annotations

import json
import re
import uuid
from app.models.appointment import Appointment
from app.models.call import Call, CallDirection
from app.models.conversation import Conversation, ConversationSource
from app.models.tenant import Tenant
from app.models.user import User
from app.services.ai_service import AIService
from app.services.appointment_availability_service import AppointmentAvailabilityService


def _authenticated_tenant(client) -> tuple[dict[str, str], str]:
    email = f"appointment-api-{uuid.uuid4().hex}@example.com"
    password = "Password123!"
    assert client.post(
        "/auth/register",
        json={"email": email, "password": password, "full_name": "Randevu User", "terms_accepted": True, "privacy_notice_acknowledged": True, "terms_version": "2026-08-04", "privacy_version": "2026-08-04", "kvkk_notice_version": "2026-08-04"},
    ).status_code == 201
    verification = client.post("/auth/email-verification/request", json={"email": email})
    code = re.search(r"(\d{6})", verification.json()["message"]).group(1)
    assert client.post(
        "/auth/email-verification/confirm",
        json={"email": email, "code": code},
    ).status_code == 200
    token = client.post(
        "/auth/login",
        json={"email": email, "password": password},
    ).json()["access_token"]
    tenant = client.post(
        "/tenants",
        json={"name": "Randevu API İşletmesi"},
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    return {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": tenant["id"],
    }, tenant["id"]


def _tenant_with_schedule(db):
    user = User(
        email=f"availability-{uuid.uuid4().hex}@example.com",
        password_hash="unused",
        full_name="Availability Test",
    )
    db.add(user)
    db.flush()
    tenant = Tenant(
        name="Randevu İşletmesi",
        slug=f"availability-{uuid.uuid4().hex}",
        owner_id=user.id,
        settings={
            "appointment_settings": {
                "configured": True,
                "timezone": "UTC",
                "minimum_notice_hours": 0,
                "booking_window_days": 30,
                "slot_interval_minutes": 30,
                "booking_location": "Online",
                "booking_notes": "",
                "services": [
                    {"id": "consultation", "name": "Danışmanlık", "duration_minutes": 60, "active": True},
                ],
                "weekly_hours": {
                    day: {"enabled": True, "start": "00:00", "end": "23:59"}
                    for day in ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
                },
                "closed_dates": [],
            }
        },
    )
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return user, tenant


def test_availability_excludes_existing_appointment(client):
    from app.db import session as session_module

    db = session_module.SessionLocal()
    try:
        user, tenant = _tenant_with_schedule(db)
        service = AppointmentAvailabilityService(db)
        initial = service.get_available_slots(tenant, days=2, service_id="consultation", limit=10)
        assert initial["reliable"] is True
        assert initial["slots"]
        occupied = initial["slots"][0]
        db.add(Appointment(
            tenant_id=tenant.id,
            created_by=user.id,
            customer_name="Mevcut müşteri",
            subject="Danışmanlık",
            starts_at=occupied["start_at"],
            duration_minutes=60,
            status="scheduled",
        ))
        db.commit()

        refreshed = service.get_available_slots(tenant, days=2, service_id="consultation", limit=20)
        assert all(item["start_at"] != occupied["start_at"] for item in refreshed["slots"])
    finally:
        db.close()


def test_appointment_settings_api_requires_configuration_before_slots(client):
    headers, _ = _authenticated_tenant(client)
    initial = client.get("/appointments/settings", headers=headers)
    assert initial.status_code == 200
    assert initial.json()["configured"] is False

    before = client.get("/appointments/availability?days=7", headers=headers)
    assert before.status_code == 200
    assert before.json()["slots"] == []

    payload = initial.json()
    payload["timezone"] = "UTC"
    payload["minimum_notice_hours"] = 0
    payload["weekly_hours"] = {
        day: {"enabled": True, "start": "00:00", "end": "23:59"}
        for day in payload["weekly_hours"]
    }
    saved = client.patch("/appointments/settings", headers=headers, json=payload)
    assert saved.status_code == 200, saved.text
    assert saved.json()["configured"] is True

    after = client.get("/appointments/availability?days=2", headers=headers)
    assert after.status_code == 200
    assert after.json()["slots"]


def test_ai_action_books_only_a_current_slot(client):
    from app.db import session as session_module
    from app.models.bot import Bot

    db = session_module.SessionLocal()
    try:
        _, tenant = _tenant_with_schedule(db)
        bot = Bot(
            tenant_id=tenant.id,
            name="Randevu Asistanı",
            description="Test",
            welcome_message="Merhaba",
            language="tr",
            primary_color="#000000",
            widget_position="right",
            is_active=True,
        )
        db.add(bot)
        db.flush()
        conversation = Conversation(
            bot_id=bot.id,
            external_user_id="905551112233",
            source=ConversationSource.WHATSAPP.value,
            extra_data={"contact_name": "Ayşe", "phone_number": "+905551112233"},
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)

        service = AppointmentAvailabilityService(db)
        slot = service.get_available_slots(tenant, days=2, service_id="consultation", limit=1)["slots"][0]
        action = {
            "type": "book_appointment",
            "service_id": "consultation",
            "start_at": slot["start_at"].isoformat() + "Z",
        }
        reply = f"Randevunuzu oluşturdum. <svontai_action>{json.dumps(action)}</svontai_action>"
        clean, appointment = service.apply_ai_action(tenant=tenant, conversation=conversation, reply=reply)
        assert appointment is None
        assert "onaylıyor musunuz" in clean
        from app.models.message import Message
        db.add(Message(conversation_id=conversation.id, sender="user", content="Evet onaylıyorum"))
        db.commit()
        clean, appointment = service.apply_ai_action(tenant=tenant, conversation=conversation, reply=reply)
        assert clean == "Randevunuzu oluşturdum."
        assert appointment is not None
        assert appointment.customer_name == "Ayşe"
        assert appointment.customer_phone == "+905551112233"
        assert appointment.source == "ai_conversation"

        _, duplicate = service.apply_ai_action(tenant=tenant, conversation=conversation, reply=reply)
        assert duplicate is None
        assert db.query(Appointment).filter(Appointment.conversation_id == conversation.id).count() == 1
    finally:
        db.close()


def test_ai_action_books_voice_call_once(client):
    from app.db import session as session_module

    db = session_module.SessionLocal()
    try:
        _, tenant = _tenant_with_schedule(db)
        call = Call(
            tenant_id=tenant.id,
            provider="twilio",
            provider_call_id=f"CA-{uuid.uuid4().hex}",
            direction=CallDirection.OUTBOUND.value,
            status="in_progress",
            from_number="tel:+12404106113",
            to_number="tel:+905551112233",
        )
        db.add(call)
        db.commit()
        db.refresh(call)

        service = AppointmentAvailabilityService(db)
        slot = service.get_available_slots(tenant, days=2, service_id="consultation", limit=1)["slots"][0]
        action = {
            "type": "book_appointment",
            "service_id": "consultation",
            "start_at": slot["start_at"].isoformat() + "Z",
        }
        reply = f"Randevunuzu oluşturdum. <svontai_action>{json.dumps(action)}</svontai_action>"

        _, unconfirmed = service.apply_ai_action(tenant=tenant, call=call, reply=reply)
        assert unconfirmed is None
        call.meta_json = {"voice_booking": {"stage": "awaiting_confirmation", "selected": action}}
        db.commit()
        clean, appointment = service.apply_ai_action(tenant=tenant, call=call, reply=reply, confirmation_text="Evet onaylıyorum")
        assert clean == "Randevunuzu oluşturdum."
        assert appointment is not None
        assert appointment.call_id == call.id
        assert appointment.conversation_id is None
        assert appointment.customer_phone == "+905551112233"
        assert appointment.source == "ai_voice"
        assert appointment.calendar_sync_status == "pending"

        _, duplicate = service.apply_ai_action(tenant=tenant, call=call, reply=reply)
        assert duplicate is None
        assert db.query(Appointment).filter(Appointment.call_id == call.id).count() == 1
    finally:
        db.close()


def test_repeated_greeting_is_removed_after_first_bot_message():
    first = type("MessageStub", (), {"sender": "bot"})()
    cleaned = AIService._remove_repeated_greeting(
        "Merhaba Döğüncü İşletmesi, yarın 14.00 uygundur.",
        [first],
    )
    assert cleaned == "yarın 14.00 uygundur."


def test_ai_action_requires_explicit_customer_confirmation(client):
    """A06: a model-emitted book_appointment action is a proposal, never consent."""
    from datetime import timedelta

    from app.core.time import utc_now_naive
    from app.db import session as session_module
    from app.models.bot import Bot
    from app.models.message import Message

    db = session_module.SessionLocal()
    try:
        _, tenant = _tenant_with_schedule(db)
        bot = Bot(tenant_id=tenant.id, name="Randevu Asistanı", language="tr", is_active=True)
        db.add(bot)
        db.flush()
        conversation = Conversation(
            bot_id=bot.id,
            external_user_id="905551112244",
            source=ConversationSource.WHATSAPP.value,
            extra_data={"contact_name": "Mehmet", "phone_number": "+905551112244"},
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)

        service = AppointmentAvailabilityService(db)
        slots = service.get_available_slots(tenant, days=2, service_id="consultation", limit=2)["slots"]
        first_slot, second_slot = slots[0], slots[1]

        def action_reply(slot):
            action = {"type": "book_appointment", "service_id": "consultation", "start_at": slot["start_at"].isoformat() + "Z"}
            return f"Randevunuzu oluşturdum. <svontai_action>{json.dumps(action)}</svontai_action>"

        def say(text: str) -> Message:
            message = Message(conversation_id=conversation.id, sender="user", content=text)
            db.add(message)
            db.commit()
            db.refresh(conversation)
            return message

        def booked() -> int:
            return db.query(Appointment).filter(Appointment.conversation_id == conversation.id).count()

        # 1. No customer message at all: nothing is booked, a proposal is recorded instead.
        clean, appointment = service.apply_ai_action(tenant=tenant, conversation=conversation, reply=action_reply(first_slot))
        assert appointment is None and booked() == 0
        assert "onaylıyor musunuz" in clean
        db.refresh(conversation)
        assert conversation.extra_data["pending_booking"]["service_id"] == "consultation"

        # 2. Customer asks a question instead of confirming.
        say("Başka saat var mı?")
        _, appointment = service.apply_ai_action(tenant=tenant, conversation=conversation, reply=action_reply(first_slot))
        assert appointment is None and booked() == 0

        # 3. Customer says something that merely contains a yes-word.
        say("Evet ama önce fiyatı öğrenmek istiyorum")
        _, appointment = service.apply_ai_action(tenant=tenant, conversation=conversation, reply=action_reply(first_slot))
        assert appointment is None and booked() == 0

        # 4. The message that triggered the proposal cannot double as its confirmation.
        say("Evet")
        db.refresh(conversation)
        pending = dict(conversation.extra_data["pending_booking"])
        latest = db.query(Message).filter(Message.conversation_id == conversation.id).order_by(Message.created_at.desc(), Message.id.desc()).first()
        conversation.extra_data = {**conversation.extra_data, "pending_booking": {**pending, "source_message_id": str(latest.id)}}
        db.commit()
        _, appointment = service.apply_ai_action(tenant=tenant, conversation=conversation, reply=action_reply(first_slot))
        assert appointment is None and booked() == 0

        # 5. An explicit yes for a *different* slot than the one proposed does not book either.
        say("Evet onaylıyorum")
        _, appointment = service.apply_ai_action(tenant=tenant, conversation=conversation, reply=action_reply(second_slot))
        assert appointment is None and booked() == 0
        db.refresh(conversation)
        assert conversation.extra_data["pending_booking"]["start_at"] == second_slot["start_at"].isoformat()

        # 6. An expired proposal must be re-offered, not booked.
        say("Evet onaylıyorum")
        db.refresh(conversation)
        conversation.extra_data = {**conversation.extra_data, "pending_booking": {
            **conversation.extra_data["pending_booking"],
            "expires_at": (utc_now_naive() - timedelta(minutes=1)).isoformat(),
        }}
        db.commit()
        clean, appointment = service.apply_ai_action(tenant=tenant, conversation=conversation, reply=action_reply(second_slot))
        assert appointment is None and booked() == 0
        assert "onaylıyor musunuz" in clean

        # 7. Explicit confirmation of the currently pending slot books exactly once.
        say("Onaylıyorum")
        clean, appointment = service.apply_ai_action(tenant=tenant, conversation=conversation, reply=action_reply(second_slot))
        assert appointment is not None
        assert clean == "Randevunuzu oluşturdum."
        assert appointment.starts_at == second_slot["start_at"]
        assert appointment.customer_name == "Mehmet"
        assert "Müşteri onay mesajı" in (appointment.notes or "")
        assert booked() == 1
        db.refresh(conversation)
        assert "pending_booking" not in (conversation.extra_data or {})
    finally:
        db.close()
