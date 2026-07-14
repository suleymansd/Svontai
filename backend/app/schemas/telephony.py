from pydantic import BaseModel, ConfigDict, Field


class TelephonyNumberCreate(BaseModel):
    provider: str = Field(default="twilio", max_length=40)
    phone_number: str = Field(..., min_length=6, max_length=60)
    label: str | None = Field(default=None, max_length=140)
    is_active: bool = True
    meta_json: dict = Field(default_factory=dict)


class TelephonyNumberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    provider: str
    phone_number: str
    label: str | None = None
    is_active: bool
    meta_json: dict
    created_at: str
    updated_at: str


class TelephonyResolveResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    tenant_id: str = Field(..., alias="tenantId")
    provider: str
    phone_number: str = Field(..., alias="phoneNumber")

