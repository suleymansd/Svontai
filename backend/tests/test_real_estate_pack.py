from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

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
