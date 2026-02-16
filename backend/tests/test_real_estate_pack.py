from __future__ import annotations

import copy
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.encryption import decrypt_token
from app.db.base import Base
import app.models  # noqa: F401
from app.models.bot import Bot
from app.models.conversation import Conversation, ConversationSource
from app.models.lead import Lead
from app.models.real_estate import RealEstateLeadListingEvent, RealEstateListing
from app.models.tenant import Tenant
from app.models.user import User
from app.services.pdf_service import SimplePdfService
from app.services.real_estate_service import RealEstateService


def _build_session():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    return SessionLocal()


def test_real_estate_intent_parser_extracts_core_fields():
    db = _build_session()
    service = RealEstateService(db)

    parsed = service.parse_message("Ankara Çankaya'da satılık 3+1 daire bakıyorum, bütçe 4-5 milyon, 140 m2")

    assert parsed["intent"] == "buyer"
    assert parsed["sale_rent"] == "sale"
    assert parsed["property_type"] == "daire"
    assert parsed["location_text"] is not None
    assert parsed["budget_max"] is not None
    assert parsed["rooms"] == "3+1"
    assert parsed["m2_min"] == 140

    db.close()


def test_real_estate_state_machine_matches_listings():
    db = _build_session()
    service = RealEstateService(db)

    owner = User(
        email="owner@test.com",
        password_hash="hash",
        full_name="Owner",
        is_admin=False,
        is_active=True,
    )
    db.add(owner)
    db.flush()

    tenant = Tenant(name="Acme Homes", owner_id=owner.id, settings={})
    db.add(tenant)
    db.flush()

    bot = Bot(tenant_id=tenant.id, name="Homes Bot", welcome_message="Merhaba!")
    db.add(bot)
    db.flush()

    conversation = Conversation(
        bot_id=bot.id,
        external_user_id="+905551112233",
        source=ConversationSource.WHATSAPP.value,
        extra_data={},
    )
    db.add(conversation)
    db.flush()

    listing = RealEstateListing(
        tenant_id=tenant.id,
        created_by=owner.id,
        title="Çankaya 3+1 Ferah Daire",
        sale_rent="sale",
        property_type="daire",
        location_text="Ankara Çankaya",
        price=4_700_000,
        currency="TRY",
        rooms="3+1",
        m2=145,
        features={},
        media=[],
        url="https://example.com/listing-1",
        is_active=True,
    )
    db.add(listing)
    db.commit()

    service.upsert_settings(tenant.id, {"enabled": True, "persona": "pro"})

    result = service.handle_inbound_whatsapp_message(
        tenant_id=tenant.id,
        bot=bot,
        conversation=conversation,
        from_number="+90 555 111 22 33",
        contact_name="Ali",
        text="Ankara Çankaya'da satılık 3+1 daire arıyorum, bütçe 5 milyon",
    )

    assert result.handled is True
    assert result.response_text is not None
    assert "Çankaya 3+1 Ferah Daire" in result.response_text
    assert "https://example.com/listing-1" in result.response_text

    db.close()


def test_personalized_suggestions_boost_clicked_history():
    db = _build_session()
    service = RealEstateService(db)

    owner = User(
        email="owner2@test.com",
        password_hash="hash",
        full_name="Owner2",
        is_admin=False,
        is_active=True,
    )
    db.add(owner)
    db.flush()

    tenant = Tenant(name="Acme Homes 2", owner_id=owner.id, settings={})
    db.add(tenant)
    db.flush()

    bot = Bot(tenant_id=tenant.id, name="Homes Bot 2", welcome_message="Merhaba!")
    db.add(bot)
    db.flush()

    conversation = Conversation(
        bot_id=bot.id,
        external_user_id="+905551119999",
        source=ConversationSource.WHATSAPP.value,
        extra_data={},
    )
    db.add(conversation)
    db.flush()

    listing_1 = RealEstateListing(
        tenant_id=tenant.id,
        created_by=owner.id,
        title="Çankaya 3+1 Daire A",
        sale_rent="sale",
        property_type="daire",
        location_text="Ankara Çankaya",
        price=4_600_000,
        currency="TRY",
        rooms="3+1",
        m2=140,
        features={},
        media=[],
        url="https://example.com/listing-a",
        is_active=True,
    )
    listing_2 = RealEstateListing(
        tenant_id=tenant.id,
        created_by=owner.id,
        title="Çankaya 3+1 Daire B",
        sale_rent="sale",
        property_type="daire",
        location_text="Ankara Çankaya",
        price=4_700_000,
        currency="TRY",
        rooms="3+1",
        m2=142,
        features={},
        media=[],
        url="https://example.com/listing-b",
        is_active=True,
    )
    db.add(listing_1)
    db.add(listing_2)
    db.commit()

    service.upsert_settings(tenant.id, {"enabled": True, "persona": "pro"})
    service.handle_inbound_whatsapp_message(
        tenant_id=tenant.id,
        bot=bot,
        conversation=conversation,
        from_number="+90 555 111 99 99",
        contact_name="Ayşe",
        text="Ankara Çankaya'da satılık 3+1 daire arıyorum, bütçe 5 milyon",
    )

    lead = db.query(Lead).filter(Lead.tenant_id == tenant.id).first()
    assert lead is not None

    db.add(
        RealEstateLeadListingEvent(
            tenant_id=tenant.id,
            lead_id=lead.id,
            listing_id=listing_2.id,
            event="clicked",
            meta_json={},
        )
    )
    db.commit()

    suggestions = service.suggest_listings_for_lead(tenant.id, lead.id)
    assert suggestions
    assert suggestions[0].id == listing_2.id

    db.close()


def test_simple_pdf_service_returns_valid_header():
    pdf_bytes = SimplePdfService.build_text_pdf(
        title="SvontAI Test PDF",
        lines=["Satir 1", "Satir 2"],
        footer="Footer",
    )
    assert pdf_bytes.startswith(b"%PDF-")


def test_pdf_limit_is_enforced():
    db = _build_session()
    service = RealEstateService(db)

    owner = User(
        email="owner3@test.com",
        password_hash="hash",
        full_name="Owner3",
        is_admin=False,
        is_active=True,
    )
    db.add(owner)
    db.flush()

    tenant = Tenant(name="Acme Homes 3", owner_id=owner.id, settings={})
    db.add(tenant)
    db.flush()

    listing = RealEstateListing(
        tenant_id=tenant.id,
        created_by=owner.id,
        title="Test Listing",
        sale_rent="sale",
        property_type="daire",
        location_text="Ankara Çankaya",
        price=4_100_000,
        currency="TRY",
        rooms="2+1",
        m2=120,
        features={},
        media=[],
        url="https://example.com/listing-limit",
        is_active=True,
    )
    db.add(listing)
    db.commit()

    service.upsert_settings(tenant.id, {"enabled": True, "pdf_limit_monthly": 1})
    _, pdf1, _ = service.generate_listing_summary_pdf(tenant.id, [listing.id])
    assert pdf1.startswith(b"%PDF-")

    try:
        service.generate_listing_summary_pdf(tenant.id, [listing.id])
        assert False, "Expected pdf_limit_reached"
    except ValueError as exc:
        assert str(exc) == "pdf_limit_reached"

    db.close()


def test_available_slots_manual_availability():
    db = _build_session()
    service = RealEstateService(db)

    owner = User(
        email="owner4@test.com",
        password_hash="hash",
        full_name="Owner4",
        is_admin=False,
        is_active=True,
    )
    db.add(owner)
    db.flush()

    tenant = Tenant(name="Acme Homes 4", owner_id=owner.id, settings={})
    db.add(tenant)
    db.flush()

    service.upsert_settings(
        tenant.id,
        {
            "enabled": True,
            "manual_availability": [
                {"weekday": 0, "start": "10:00", "end": "12:00"}
            ],
            "google_calendar_enabled": False,
        },
    )

    start_at = datetime(2026, 2, 16, 9, 0, 0)  # Monday
    end_at = datetime(2026, 2, 16, 18, 0, 0)
    slots = service.get_available_slots(
        tenant_id=tenant.id,
        agent_id=owner.id,
        start_at=start_at,
        end_at=end_at,
        duration_minutes=60,
        step_minutes=60,
    )

    assert any(slot["start_at"].startswith("2026-02-16T10:00") for slot in slots)
    assert any(slot["start_at"].startswith("2026-02-16T11:00") for slot in slots)
    assert not any(slot["start_at"].startswith("2026-02-16T09:00") for slot in slots)

    db.close()


def test_google_sheets_sync_creates_and_updates_listings():
    db = _build_session()
    service = RealEstateService(db)

    owner = User(
        email="owner-sheets@test.com",
        password_hash="hash",
        full_name="Owner Sheets",
        is_admin=False,
        is_active=True,
    )
    db.add(owner)
    db.flush()

    tenant = Tenant(name="Sheets Tenant", owner_id=owner.id, settings={})
    db.add(tenant)
    db.flush()

    existing = RealEstateListing(
        tenant_id=tenant.id,
        created_by=owner.id,
        title="Eski İlan",
        sale_rent="sale",
        property_type="daire",
        location_text="Ankara",
        price=2_500_000,
        currency="TRY",
        rooms="2+1",
        m2=100,
        features={"_source": "google_sheets", "_external_id": "X1"},
        media=[],
        url="https://example.com/old-x1",
        is_active=True,
    )
    db.add(existing)
    db.commit()

    csv_text = (
        "id,title,sale_rent,property_type,location_text,price,currency,m2,rooms,url\n"
        "X1,Çankaya Güncel İlan,sale,daire,Ankara Çankaya,3100000,TRY,120,3+1,https://example.com/x1\n"
        "X2,Yeni İlan,rent,daire,Ankara Keçiören,24000,TRY,95,2+1,https://example.com/x2\n"
    )
    service._http_get_text = lambda url, headers=None: csv_text  # type: ignore[assignment]

    result = service.sync_listings_from_google_sheets(
        tenant_id=tenant.id,
        user_id=owner.id,
        config={
            "sheet_url": "https://docs.google.com/spreadsheets/d/test-sheet-id/edit#gid=0",
            "save_to_settings": True,
        },
    )

    assert result["source"] == "google_sheets"
    assert result["stats"]["updated"] == 1
    assert result["stats"]["created"] == 1
    assert result["stats"]["skipped"] == 0

    listings = db.query(RealEstateListing).filter(RealEstateListing.tenant_id == tenant.id).all()
    assert len(listings) == 2
    updated = next(
        (
            item
            for item in listings
            if (item.features or {}).get("_external_id") == "X1"
        ),
        None,
    )
    assert updated is not None
    assert updated.title == "Çankaya Güncel İlan"
    assert int(updated.price) == 3_100_000

    settings = service.get_or_create_settings(tenant.id)
    google_cfg = settings.listings_source.get("google_sheets") or {}
    assert google_cfg.get("enabled") is True
    assert google_cfg.get("last_sync_at")

    db.close()


def test_remax_sync_deactivates_missing_and_encrypts_api_key():
    db = _build_session()
    service = RealEstateService(db)

    owner = User(
        email="owner-remax@test.com",
        password_hash="hash",
        full_name="Owner Remax",
        is_admin=False,
        is_active=True,
    )
    db.add(owner)
    db.flush()

    tenant = Tenant(name="Remax Tenant", owner_id=owner.id, settings={})
    db.add(tenant)
    db.flush()

    listing_a = RealEstateListing(
        tenant_id=tenant.id,
        created_by=owner.id,
        title="A İlan",
        sale_rent="sale",
        property_type="daire",
        location_text="Ankara",
        price=4_000_000,
        currency="TRY",
        rooms="3+1",
        m2=135,
        features={"_source": "remax_connector", "_external_id": "A"},
        media=[],
        url="https://example.com/a",
        is_active=True,
    )
    listing_b = RealEstateListing(
        tenant_id=tenant.id,
        created_by=owner.id,
        title="B İlan",
        sale_rent="sale",
        property_type="daire",
        location_text="Ankara",
        price=4_200_000,
        currency="TRY",
        rooms="3+1",
        m2=138,
        features={"_source": "remax_connector", "_external_id": "B"},
        media=[],
        url="https://example.com/b",
        is_active=True,
    )
    db.add(listing_a)
    db.add(listing_b)
    db.commit()

    service._http_get_json = lambda url, headers=None: {  # type: ignore[assignment]
        "data": {
            "listings": [
                {
                    "id": "A",
                    "title": "A İlan Güncel",
                    "sale_rent": "sale",
                    "property_type": "daire",
                    "location_text": "Ankara Çankaya",
                    "price": 4_300_000,
                    "currency": "TRY",
                    "m2": 140,
                    "rooms": "3+1",
                    "url": "https://example.com/a",
                }
            ]
        }
    }

    result = service.sync_listings_from_remax_connector(
        tenant_id=tenant.id,
        user_id=owner.id,
        config={
            "endpoint_url": "https://remax.example.com/api/listings",
            "response_path": "data.listings",
            "api_key": "secret-key-123",
            "deactivate_missing": True,
            "save_to_settings": True,
        },
    )

    assert result["source"] == "remax_connector"
    assert result["stats"]["updated"] == 1
    assert result["stats"]["deactivated"] == 1

    refreshed_a = db.query(RealEstateListing).filter(RealEstateListing.id == listing_a.id).first()
    refreshed_b = db.query(RealEstateListing).filter(RealEstateListing.id == listing_b.id).first()
    assert refreshed_a is not None and refreshed_a.is_active is True
    assert refreshed_a.title == "A İlan Güncel"
    assert refreshed_b is not None and refreshed_b.is_active is False

    settings = service.get_or_create_settings(tenant.id)
    remax_cfg = settings.listings_source.get("remax_connector") or {}
    encrypted = remax_cfg.get("api_key_encrypted") or ""
    assert encrypted
    assert decrypt_token(encrypted) == "secret-key-123"
    assert not remax_cfg.get("api_key")

    db.close()


def test_connector_auto_sync_runs_only_when_due():
    db = _build_session()
    service = RealEstateService(db)

    owner = User(
        email="owner-auto-sync@test.com",
        password_hash="hash",
        full_name="Owner Auto",
        is_admin=False,
        is_active=True,
    )
    db.add(owner)
    db.flush()

    tenant = Tenant(name="Auto Sync Tenant", owner_id=owner.id, settings={})
    db.add(tenant)
    db.flush()

    service.upsert_settings(
        tenant.id,
        {
            "enabled": True,
            "listings_source": {
                "google_sheets": {
                    "enabled": True,
                    "auto_sync": True,
                    "sync_interval_minutes": 60,
                    "csv_url": "https://example.com/sheet.csv",
                },
                "remax_connector": {
                    "enabled": True,
                    "auto_sync": True,
                    "sync_interval_minutes": 60,
                    "endpoint_url": "https://example.com/remax",
                },
            },
        },
    )

    calls: list[str] = []

    def fake_google(tenant_id, user_id, config):
        calls.append("google")
        return {"source": "google_sheets", "stats": {"created": 1, "updated": 0, "deactivated": 0, "skipped": 0}, "synced_at": datetime.utcnow().isoformat()}

    def fake_remax(tenant_id, user_id, config):
        calls.append("remax")
        return {"source": "remax_connector", "stats": {"created": 1, "updated": 0, "deactivated": 0, "skipped": 0}, "synced_at": datetime.utcnow().isoformat()}

    service.sync_listings_from_google_sheets = fake_google  # type: ignore[assignment]
    service.sync_listings_from_remax_connector = fake_remax  # type: ignore[assignment]

    result_first = service.run_connector_auto_sync(tenant.id)
    assert set(calls) == {"google", "remax"}
    assert result_first["google_sheets"]["status"] == "ok"
    assert result_first["remax_connector"]["status"] == "ok"

    settings = service.get_or_create_settings(tenant.id)
    source = copy.deepcopy(settings.listings_source)
    source["google_sheets"]["last_sync_at"] = datetime.utcnow().isoformat()
    source["remax_connector"]["last_sync_at"] = datetime.utcnow().isoformat()
    settings.listings_source = source
    db.commit()

    calls.clear()
    result_second = service.run_connector_auto_sync(tenant.id)
    assert calls == []
    assert result_second["google_sheets"]["status"] == "skipped"
    assert result_second["google_sheets"]["reason"] == "not_due"
    assert result_second["remax_connector"]["status"] == "skipped"
    assert result_second["remax_connector"]["reason"] == "not_due"

    db.close()
