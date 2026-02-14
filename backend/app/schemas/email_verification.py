"""
Schemas for email verification flow.
"""

from pydantic import BaseModel, EmailStr, Field


class EmailVerificationRequest(BaseModel):
    email: EmailStr


class EmailVerificationConfirmRequest(BaseModel):
    email: EmailStr
    code: str = Field(min_length=4, max_length=10)


class EmailVerificationResponse(BaseModel):
    success: bool = True
    message: str
