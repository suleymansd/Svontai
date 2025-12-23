"""
Pydantic schemas for WhatsApp integration.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class WhatsAppIntegrationBase(BaseModel):
    """Base schema for WhatsApp integration."""
    whatsapp_phone_number_id: str
    whatsapp_business_account_id: str
    access_token: str
    webhook_verify_token: str


class WhatsAppIntegrationCreate(WhatsAppIntegrationBase):
    """Schema for creating WhatsApp integration."""
    pass


class WhatsAppIntegrationUpdate(BaseModel):
    """Schema for updating WhatsApp integration."""
    whatsapp_phone_number_id: str | None = None
    whatsapp_business_account_id: str | None = None
    access_token: str | None = None
    webhook_verify_token: str | None = None
    is_active: bool | None = None


class WhatsAppIntegrationResponse(BaseModel):
    """Schema for WhatsApp integration response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    tenant_id: UUID
    bot_id: UUID | None
    whatsapp_phone_number_id: str
    whatsapp_business_account_id: str
    webhook_verify_token: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    # Note: access_token is intentionally excluded for security


class WhatsAppWebhookVerification(BaseModel):
    """Schema for WhatsApp webhook verification."""
    hub_mode: str | None = None
    hub_verify_token: str | None = None
    hub_challenge: str | None = None

