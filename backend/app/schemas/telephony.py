from pydantic import BaseModel, Field


class TelephonyNumberCreate(BaseModel):
    provider: str = Field(default="twilio", max_length=40)
    phone_number: str = Field(..., min_length=6, max_length=60)
    label: str | None = Field(default=None, max_length=140)
    is_active: bool = True
    meta_json: dict = Field(default_factory=dict)


class TelephonyNumberResponse(BaseModel):
    id: str
    tenant_id: str
    provider: str
    phone_number: str
    label: str | None = None
    is_active: bool
    meta_json: dict
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class TelephonyResolveResponse(BaseModel):
    tenant_id: str = Field(..., alias="tenantId")
    provider: str
    phone_number: str = Field(..., alias="phoneNumber")

    class Config:
        populate_by_name = True

