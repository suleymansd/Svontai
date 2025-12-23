"""
Onboarding service for managing WhatsApp setup flow.
"""

import secrets
import json
from uuid import UUID
from datetime import datetime
from typing import Optional, Dict, Any, List

from sqlalchemy.orm import Session

from app.models.whatsapp_account import WhatsAppAccount, TokenStatus, WebhookStatus
from app.models.onboarding import (
    OnboardingStep, 
    OnboardingProvider, 
    StepStatus,
    AuditLog,
    WHATSAPP_ONBOARDING_STEPS
)
from app.core.encryption import encrypt_token, decrypt_token
from app.services.meta_api import meta_api_service, MetaAPIError
from app.core.config import settings


class OnboardingService:
    """Service for managing WhatsApp onboarding flow."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_audit_log(
        self,
        tenant_id: UUID,
        action: str,
        user_id: Optional[UUID] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        payload: Optional[Dict] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> AuditLog:
        """Create an audit log entry."""
        log = AuditLog(
            tenant_id=tenant_id,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            payload_json=payload,
            ip_address=ip_address,
            user_agent=user_agent
        )
        self.db.add(log)
        self.db.commit()
        return log
    
    def initialize_onboarding_steps(self, tenant_id: UUID) -> List[OnboardingStep]:
        """
        Initialize all WhatsApp onboarding steps for a tenant.
        
        Args:
            tenant_id: The tenant ID.
            
        Returns:
            List of created OnboardingStep objects.
        """
        # Delete any existing steps for this tenant/provider
        self.db.query(OnboardingStep).filter(
            OnboardingStep.tenant_id == tenant_id,
            OnboardingStep.provider == OnboardingProvider.WHATSAPP.value
        ).delete()
        
        steps = []
        for step_config in WHATSAPP_ONBOARDING_STEPS:
            step = OnboardingStep(
                tenant_id=tenant_id,
                provider=OnboardingProvider.WHATSAPP.value,
                step_key=step_config["step_key"],
                step_order=step_config["step_order"],
                step_name=step_config["step_name"],
                step_description=step_config["step_description"],
                status=StepStatus.PENDING.value
            )
            steps.append(step)
            self.db.add(step)
        
        self.db.commit()
        return steps
    
    def get_onboarding_steps(self, tenant_id: UUID) -> List[OnboardingStep]:
        """Get all onboarding steps for a tenant."""
        return self.db.query(OnboardingStep).filter(
            OnboardingStep.tenant_id == tenant_id,
            OnboardingStep.provider == OnboardingProvider.WHATSAPP.value
        ).order_by(OnboardingStep.step_order).all()
    
    def update_step_status(
        self,
        tenant_id: UUID,
        step_key: str,
        status: StepStatus,
        message: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Optional[OnboardingStep]:
        """
        Update the status of an onboarding step.
        
        Args:
            tenant_id: The tenant ID.
            step_key: The step identifier.
            status: New status.
            message: Optional status message.
            metadata: Optional metadata dict.
            
        Returns:
            Updated OnboardingStep or None if not found.
        """
        step = self.db.query(OnboardingStep).filter(
            OnboardingStep.tenant_id == tenant_id,
            OnboardingStep.provider == OnboardingProvider.WHATSAPP.value,
            OnboardingStep.step_key == step_key
        ).first()
        
        if not step:
            return None
        
        step.status = status.value
        step.message = message
        step.updated_at = datetime.utcnow()
        
        if status == StepStatus.IN_PROGRESS and not step.started_at:
            step.started_at = datetime.utcnow()
        elif status == StepStatus.DONE:
            step.completed_at = datetime.utcnow()
        
        if metadata:
            step.metadata_json = {**(step.metadata_json or {}), **metadata}
        
        self.db.commit()
        return step
    
    def get_or_create_whatsapp_account(self, tenant_id: UUID) -> WhatsAppAccount:
        """Get existing or create new WhatsApp account for tenant."""
        account = self.db.query(WhatsAppAccount).filter(
            WhatsAppAccount.tenant_id == tenant_id
        ).first()
        
        if not account:
            verify_token = meta_api_service.generate_verify_token()
            account = WhatsAppAccount(
                tenant_id=tenant_id,
                webhook_verify_token=verify_token
            )
            self.db.add(account)
            self.db.commit()
            self.db.refresh(account)
        
        return account
    
    def start_onboarding(self, tenant_id: UUID) -> Dict[str, Any]:
        """
        Start the WhatsApp onboarding process.
        
        Args:
            tenant_id: The tenant ID.
            
        Returns:
            Dict with OAuth URL and setup configuration.
        """
        # Initialize steps
        self.initialize_onboarding_steps(tenant_id)
        
        # Get or create WhatsApp account
        account = self.get_or_create_whatsapp_account(tenant_id)
        
        # Update first step to in_progress
        self.update_step_status(tenant_id, "start_setup", StepStatus.DONE)
        self.update_step_status(tenant_id, "meta_auth", StepStatus.IN_PROGRESS)
        
        # Generate state for OAuth (includes tenant ID for callback)
        state = f"{tenant_id}:{secrets.token_urlsafe(16)}"
        
        # Get OAuth URL
        oauth_url = meta_api_service.get_oauth_url(state)
        
        # Get Embedded Signup config
        embedded_config = meta_api_service.get_embedded_signup_config(state)
        
        # Create audit log
        self.create_audit_log(
            tenant_id=tenant_id,
            action="whatsapp_onboarding_started",
            resource_type="whatsapp_account",
            resource_id=str(account.id)
        )
        
        return {
            "oauth_url": oauth_url,
            "embedded_config": embedded_config,
            "verify_token": account.webhook_verify_token,
            "state": state,
            "webhook_url": f"{settings.WEBHOOK_PUBLIC_URL or ''}/whatsapp/webhook"
        }
    
    async def process_oauth_callback(
        self,
        tenant_id: UUID,
        code: str
    ) -> WhatsAppAccount:
        """
        Process OAuth callback and complete setup.
        
        Args:
            tenant_id: The tenant ID from state.
            code: Authorization code from Meta.
            
        Returns:
            Updated WhatsAppAccount.
        """
        account = self.get_or_create_whatsapp_account(tenant_id)
        
        try:
            # Mark meta_auth as done, select_waba in progress
            self.update_step_status(tenant_id, "meta_auth", StepStatus.DONE)
            self.update_step_status(tenant_id, "select_waba", StepStatus.IN_PROGRESS)
            
            # Exchange code for token
            token_data = await meta_api_service.exchange_code_for_token(code)
            short_lived_token = token_data["access_token"]
            
            # Get long-lived token
            long_lived_data = await meta_api_service.get_long_lived_token(short_lived_token)
            access_token = long_lived_data["access_token"]
            
            # Get WABAs and phone numbers
            wabas = await meta_api_service.get_whatsapp_business_accounts(access_token)
            
            if not wabas:
                self.update_step_status(
                    tenant_id, "select_waba", StepStatus.ERROR,
                    message="WhatsApp Business hesabı bulunamadı"
                )
                raise MetaAPIError("No WhatsApp Business accounts found")
            
            waba = wabas[0]  # Use first WABA
            waba_id = waba["id"]
            
            # Get phone numbers
            phone_numbers = await meta_api_service.get_phone_numbers(access_token, waba_id)
            
            if not phone_numbers:
                self.update_step_status(
                    tenant_id, "select_waba", StepStatus.ERROR,
                    message="Telefon numarası bulunamadı"
                )
                raise MetaAPIError("No phone numbers found")
            
            phone = phone_numbers[0]  # Use first phone number
            
            self.update_step_status(tenant_id, "select_waba", StepStatus.DONE)
            self.update_step_status(tenant_id, "save_credentials", StepStatus.IN_PROGRESS)
            
            # Save credentials
            account.waba_id = waba_id
            account.phone_number_id = phone["id"]
            account.display_phone_number = phone.get("display_phone_number", "")
            account.access_token_encrypted = encrypt_token(access_token)
            account.token_status = TokenStatus.ACTIVE.value
            account.app_id = meta_api_service.app_id
            
            self.db.commit()
            
            self.update_step_status(tenant_id, "save_credentials", StepStatus.DONE)
            self.update_step_status(tenant_id, "configure_webhook", StepStatus.IN_PROGRESS)
            
            # Subscribe to webhooks
            try:
                await meta_api_service.subscribe_to_webhooks(access_token, waba_id)
                account.webhook_status = WebhookStatus.PENDING_VERIFICATION.value
                self.db.commit()
                
                self.update_step_status(tenant_id, "configure_webhook", StepStatus.DONE)
                self.update_step_status(tenant_id, "verify_webhook", StepStatus.IN_PROGRESS,
                    message="Webhook doğrulaması bekleniyor..."
                )
            except MetaAPIError as e:
                self.update_step_status(
                    tenant_id, "configure_webhook", StepStatus.ERROR,
                    message=f"Webhook hatası: {e.message}"
                )
            
            # Create audit log
            self.create_audit_log(
                tenant_id=tenant_id,
                action="whatsapp_credentials_saved",
                resource_type="whatsapp_account",
                resource_id=str(account.id),
                payload={
                    "waba_id": waba_id,
                    "phone_number_id": phone["id"],
                    "display_phone_number": phone.get("display_phone_number")
                }
            )
            
            return account
            
        except MetaAPIError as e:
            self.create_audit_log(
                tenant_id=tenant_id,
                action="whatsapp_onboarding_error",
                resource_type="whatsapp_account",
                payload={"error": e.message, "details": e.details}
            )
            raise
    
    def mark_webhook_verified(self, tenant_id: UUID) -> bool:
        """
        Mark webhook as verified after successful verification.
        
        Args:
            tenant_id: The tenant ID.
            
        Returns:
            True if successful.
        """
        account = self.db.query(WhatsAppAccount).filter(
            WhatsAppAccount.tenant_id == tenant_id
        ).first()
        
        if not account:
            return False
        
        account.webhook_status = WebhookStatus.VERIFIED.value
        account.is_verified = True
        account.is_active = True
        
        self.update_step_status(tenant_id, "verify_webhook", StepStatus.DONE)
        self.update_step_status(tenant_id, "complete", StepStatus.DONE,
            message="WhatsApp bağlantısı başarıyla tamamlandı!"
        )
        
        self.db.commit()
        
        self.create_audit_log(
            tenant_id=tenant_id,
            action="whatsapp_webhook_verified",
            resource_type="whatsapp_account",
            resource_id=str(account.id)
        )
        
        return True
    
    def get_whatsapp_account(self, tenant_id: UUID) -> Optional[WhatsAppAccount]:
        """Get WhatsApp account for tenant."""
        return self.db.query(WhatsAppAccount).filter(
            WhatsAppAccount.tenant_id == tenant_id
        ).first()
    
    def get_account_by_verify_token(self, verify_token: str) -> Optional[WhatsAppAccount]:
        """Get WhatsApp account by webhook verify token."""
        return self.db.query(WhatsAppAccount).filter(
            WhatsAppAccount.webhook_verify_token == verify_token
        ).first()
    
    def get_decrypted_token(self, account: WhatsAppAccount) -> Optional[str]:
        """Get decrypted access token for an account."""
        if not account.access_token_encrypted:
            return None
        return decrypt_token(account.access_token_encrypted)

