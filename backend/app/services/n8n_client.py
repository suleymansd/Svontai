"""
n8n Workflow Engine Client Service.

Handles communication between SvontAI and n8n workflow engine.
All WhatsApp events pass through SvontAI first, then are dispatched
to n8n for workflow execution.

Key features:
- Idempotency: Duplicate messages (same tenant_id + message_id) are detected and skipped
- Background execution: n8n calls run asynchronously to not block webhook responses
- Retry with exponential backoff: Transient failures are retried
"""

import uuid
import logging
import asyncio
from typing import Optional, Any, Tuple
from datetime import datetime

import httpx
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.core.n8n_security import generate_svontai_to_n8n_headers, create_n8n_jwt_token
from app.services.system_event_service import SystemEventService
from app.models.automation import (
    AutomationRun,
    AutomationRunStatus,
    AutomationChannel,
    TenantAutomationSettings
)
from app.models.tenant import Tenant

logger = logging.getLogger(__name__)

# Statuses that indicate a message is already being processed or was processed
IDEMPOTENT_STATUSES = {
    AutomationRunStatus.RECEIVED.value,
    AutomationRunStatus.RUNNING.value,
    AutomationRunStatus.SUCCESS.value,
}


class N8NClientError(Exception):
    """Base exception for n8n client errors."""
    pass


class N8NTimeoutError(N8NClientError):
    """Raised when n8n request times out."""
    pass


class N8NConnectionError(N8NClientError):
    """Raised when connection to n8n fails."""
    pass


class N8NClient:
    """
    Client for n8n workflow engine communication.
    
    This service handles:
    - Triggering n8n workflows for incoming messages
    - Creating and tracking automation runs
    - Retry logic for failed requests
    - Security (signature generation)
    """
    
    def __init__(self, db: Session):
        """
        Initialize n8n client.
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self.base_url = settings.N8N_BASE_URL.rstrip('/')
        self.timeout = settings.N8N_TIMEOUT_SECONDS
        self.max_retries = settings.N8N_RETRY_COUNT
    
    def is_n8n_enabled_globally(self) -> bool:
        """Check if n8n is enabled globally via settings."""
        return settings.USE_N8N
    
    def get_tenant_automation_settings(self, tenant_id: uuid.UUID) -> Optional[TenantAutomationSettings]:
        """Get automation settings for a tenant."""
        return self.db.query(TenantAutomationSettings).filter(
            TenantAutomationSettings.tenant_id == str(tenant_id)
        ).first()
    
    def should_use_n8n(self, tenant_id: uuid.UUID) -> bool:
        """
        Determine if n8n should be used for this tenant.
        
        Checks both global flag and tenant-specific settings.
        """
        # Global flag must be enabled
        if not self.is_n8n_enabled_globally():
            return False
        
        # Check tenant-specific setting
        tenant_settings = self.get_tenant_automation_settings(tenant_id)
        if tenant_settings is None:
            return False
        
        return tenant_settings.use_n8n
    
    def get_workflow_id(
        self,
        tenant_id: uuid.UUID,
        channel: str = AutomationChannel.WHATSAPP.value
    ) -> Optional[str]:
        """
        Get the workflow ID for a tenant and channel.
        
        Args:
            tenant_id: Tenant UUID
            channel: Channel type (whatsapp, web_widget)
        
        Returns:
            Workflow ID or None if not configured
        """
        tenant_settings = self.get_tenant_automation_settings(tenant_id)
        
        if tenant_settings:
            workflow_id = tenant_settings.get_workflow_id(channel)
            if workflow_id:
                return workflow_id
        
        # Fall back to global default
        return settings.N8N_INCOMING_WORKFLOW_ID or None
    
    def get_n8n_url(self, tenant_id: uuid.UUID) -> str:
        """
        Get n8n URL for a tenant (supports custom n8n instances).
        """
        tenant_settings = self.get_tenant_automation_settings(tenant_id)
        
        if tenant_settings and tenant_settings.custom_n8n_url:
            return tenant_settings.custom_n8n_url.rstrip('/')
        
        return self.base_url
    
    def check_duplicate_message(
        self,
        tenant_id: uuid.UUID,
        message_id: Optional[str]
    ) -> Tuple[bool, Optional[AutomationRun]]:
        """
        Check if a message has already been processed (idempotency check).
        
        Args:
            tenant_id: Tenant UUID
            message_id: External message ID (e.g., WhatsApp wamid)
        
        Returns:
            Tuple of (is_duplicate, existing_run)
        """
        if not message_id:
            # Cannot check idempotency without message_id
            return False, None
        
        existing_run = self.db.query(AutomationRun).filter(
            AutomationRun.tenant_id == str(tenant_id),
            AutomationRun.message_id == message_id,
            AutomationRun.status.in_(IDEMPOTENT_STATUSES)
        ).first()
        
        if existing_run:
            logger.info(
                f"Duplicate message detected: tenant={tenant_id}, message_id={message_id}, "
                f"existing_run={existing_run.id}, status={existing_run.status}"
            )
            return True, existing_run
        
        return False, None
    
    def create_automation_run(
        self,
        tenant_id: uuid.UUID,
        channel: str,
        from_number: str,
        to_number: Optional[str],
        message_id: Optional[str],
        message_content: Optional[str],
        workflow_id: Optional[str] = None,
        correlation_id: Optional[str] = None
    ) -> Tuple[AutomationRun, bool]:
        """
        Create an automation run record with idempotency handling.
        
        Uses a unique constraint on (tenant_id, message_id) to prevent duplicates.
        If a duplicate is detected, returns the existing run instead of creating a new one.
        
        Args:
            tenant_id: Tenant UUID
            channel: Channel type
            from_number: Sender number
            to_number: Recipient number
            message_id: External message ID
            message_content: Message text
            workflow_id: n8n workflow ID
        
        Returns:
            Tuple of (AutomationRun instance, is_new)
            - is_new=True: New run was created, proceed with n8n trigger
            - is_new=False: Duplicate detected, skip n8n trigger
        """
        # First, check for existing run (fast path for duplicates)
        is_duplicate, existing_run = self.check_duplicate_message(tenant_id, message_id)
        if is_duplicate and existing_run:
            return existing_run, False
        
        run = AutomationRun(
            id=str(uuid.uuid4()),
            tenant_id=str(tenant_id),
            channel=channel,
            from_number=from_number,
            to_number=to_number,
            message_id=message_id,
            message_content=message_content,
            n8n_workflow_id=workflow_id,
            status=AutomationRunStatus.RECEIVED.value,
            correlation_id=correlation_id
        )
        
        try:
            self.db.add(run)
            self.db.commit()
            self.db.refresh(run)
            
            logger.info(f"Created automation run {run.id} for tenant {tenant_id}")
            return run, True
            
        except IntegrityError as e:
            # Race condition: another request created a run for this message
            self.db.rollback()
            
            logger.warning(
                f"IntegrityError creating automation run (duplicate message_id): "
                f"tenant={tenant_id}, message_id={message_id}. Error: {e}"
            )
            
            # Fetch the existing run that won the race
            existing_run = self.db.query(AutomationRun).filter(
                AutomationRun.tenant_id == str(tenant_id),
                AutomationRun.message_id == message_id
            ).first()
            
            if existing_run:
                return existing_run, False
            
            # Shouldn't happen, but re-raise if we can't find the existing run
            raise
    
    def build_incoming_message_payload(
        self,
        tenant_id: uuid.UUID,
        channel: str,
        from_number: str,
        to_number: str,
        text: str,
        message_id: str,
        timestamp: str,
        run_id: str,
        correlation_id: Optional[str] = None,
        contact_name: Optional[str] = None,
        raw_payload: Optional[dict] = None,
        extra_data: Optional[dict] = None
    ) -> dict:
        """
        Build the payload for incoming message event to n8n.
        
        This is the standardized payload format sent to n8n workflows.
        """
        # Generate callback token for n8n to use
        callback_token = create_n8n_jwt_token(str(tenant_id))
        
        payload = {
            "event": "incoming_message",
            "runId": run_id,
            "correlationId": correlation_id,
            "tenantId": str(tenant_id),
            "channel": channel,
            "from": from_number,
            "to": to_number,
            "text": text,
            "messageId": message_id,
            "timestamp": timestamp,
            "contactName": contact_name,
            "callback": {
                "url": f"{settings.BACKEND_URL}/api/v1/channels/whatsapp/send",
                "token": callback_token
            },
            "extra": extra_data or {}
        }
        
        if raw_payload:
            payload["rawPayload"] = raw_payload
        
        return payload

    def build_event_payload(
        self,
        *,
        tenant_id: uuid.UUID,
        run_id: str,
        event_type: str,
        channel: str,
        external_event_id: str | None,
        from_id: str,
        to_id: str | None,
        text: str | None = None,
        timestamp: str | None = None,
        correlation_id: Optional[str] = None,
        contact_name: Optional[str] = None,
        raw_payload: Optional[dict] = None,
        metadata: Optional[dict] = None,
        callback_path: str = "/api/v1/channels/whatsapp/send",
    ) -> dict:
        """
        Build a normalized SvontAI event payload for n8n-first orchestration.

        This is the forward-compatible format used by WhatsApp/Web/Voice events.
        """
        callback_token = create_n8n_jwt_token(str(tenant_id))
        base_url = (settings.BACKEND_URL or "").rstrip("/")

        payload: dict = {
            "event": "svontai_event",
            "eventType": event_type,
            "runId": run_id,
            "correlationId": correlation_id,
            "tenantId": str(tenant_id),
            "channel": channel,
            "externalEventId": external_event_id,
            "from": from_id,
            "to": to_id,
            "text": text,
            "timestamp": timestamp,
            "contactName": contact_name,
            "metadata": metadata or {},
            "callback": {
                "url": f"{base_url}{callback_path}",
                "token": callback_token,
            },
        }

        if raw_payload is not None:
            payload["rawPayload"] = raw_payload

        return payload

    async def trigger_event(
        self,
        *,
        tenant_id: uuid.UUID,
        channel: str,
        workflow_id: str,
        event_type: str,
        external_event_id: str | None,
        from_id: str,
        to_id: str | None,
        text: str | None = None,
        timestamp: str | None = None,
        correlation_id: Optional[str] = None,
        contact_name: Optional[str] = None,
        raw_payload: Optional[dict] = None,
        metadata: Optional[dict] = None,
    ) -> AutomationRun:
        """
        Generic entry point for triggering n8n on normalized SvontAI events.

        Creates an AutomationRun idempotently using external_event_id (stored in message_id field for now).
        """
        # NOTE: For backward compatibility, we store external_event_id into message_id.
        # This keeps the existing unique index (tenant_id, message_id) effective.
        run, is_new = self.create_automation_run(
            tenant_id=tenant_id,
            channel=channel,
            from_number=from_id,
            to_number=to_id,
            message_id=external_event_id,
            message_content=text,
            workflow_id=workflow_id,
            correlation_id=correlation_id,
        )

        if not is_new:
            return run

        payload = self.build_event_payload(
            tenant_id=tenant_id,
            run_id=str(run.id),
            event_type=event_type,
            channel=channel,
            external_event_id=external_event_id,
            from_id=from_id,
            to_id=to_id,
            text=text,
            timestamp=timestamp,
            correlation_id=correlation_id,
            contact_name=contact_name,
            raw_payload=raw_payload,
            metadata=metadata,
        )

        # Fire-and-forget semantics are handled by the caller (background task),
        # but we keep trigger_with_retry for reuse.
        await self.trigger_with_retry(workflow_id, payload, tenant_id, run)
        return run
    
    async def trigger_workflow(
        self,
        workflow_id: str,
        payload: dict,
        tenant_id: uuid.UUID,
        run: AutomationRun
    ) -> dict:
        """
        Trigger an n8n workflow via webhook.
        
        Args:
            workflow_id: n8n workflow ID or webhook path
            payload: Event payload to send
            tenant_id: Tenant UUID
            run: AutomationRun record to update
        
        Returns:
            n8n response data
        """
        n8n_url = self.get_n8n_url(tenant_id)
        
        # Build webhook URL
        # n8n webhook URLs can be either:
        # - /webhook/{workflow_id} (production)
        # - /webhook-test/{workflow_id} (test mode)
        webhook_url = f"{n8n_url}{settings.N8N_WEBHOOK_PATH}/{workflow_id}"
        
        # Generate security headers
        headers = generate_svontai_to_n8n_headers(payload, str(tenant_id))
        
        # Add API key if configured
        if settings.N8N_API_KEY:
            headers["X-N8N-API-KEY"] = settings.N8N_API_KEY
        
        # Store request payload
        run.request_payload = payload
        run.n8n_workflow_id = workflow_id
        run.mark_running()
        self.db.commit()
        
        logger.info(f"Triggering n8n workflow {workflow_id} for run {run.id}")
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    webhook_url,
                    json=payload,
                    headers=headers
                )
                
                response.raise_for_status()
                response_data = response.json() if response.content else {}
                
                # Extract n8n execution ID if available
                n8n_execution_id = response_data.get("executionId")
                if n8n_execution_id:
                    run.n8n_execution_id = n8n_execution_id
                
                run.mark_success(response_data)
                self.db.commit()
                
                logger.info(
                    f"n8n workflow triggered successfully. "
                    f"Run: {run.id}, Execution: {n8n_execution_id}"
                )
                
                return response_data
        
        except httpx.TimeoutException as e:
            run.mark_timeout()
            self.db.commit()
            SystemEventService(self.db).log(
                tenant_id=run.tenant_id,
                source="n8n",
                level="error",
                code="N8N_TIMEOUT",
                message="n8n request timed out",
                meta_json={"run_id": run.id},
                correlation_id=run.correlation_id
            )
            logger.error(f"n8n request timed out for run {run.id}: {e}")
            raise N8NTimeoutError(f"Request timed out: {e}")
        
        except httpx.ConnectError as e:
            run.mark_failed(f"Connection error: {e}")
            self.db.commit()
            SystemEventService(self.db).log(
                tenant_id=run.tenant_id,
                source="n8n",
                level="error",
                code="N8N_CONNECT_ERROR",
                message="n8n connection error",
                meta_json={"run_id": run.id},
                correlation_id=run.correlation_id
            )
            logger.error(f"n8n connection error for run {run.id}: {e}")
            raise N8NConnectionError(f"Connection error: {e}")
        
        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP {e.response.status_code}: {e.response.text[:500]}"
            run.mark_failed(error_msg, {"status_code": e.response.status_code})
            self.db.commit()
            SystemEventService(self.db).log(
                tenant_id=run.tenant_id,
                source="n8n",
                level="error",
                code="N8N_HTTP_ERROR",
                message=error_msg[:500],
                meta_json={"run_id": run.id, "status_code": e.response.status_code},
                correlation_id=run.correlation_id
            )
            logger.error(f"n8n HTTP error for run {run.id}: {error_msg}")
            raise N8NClientError(error_msg)
        
        except Exception as e:
            run.mark_failed(str(e))
            self.db.commit()
            SystemEventService(self.db).log(
                tenant_id=run.tenant_id,
                source="n8n",
                level="error",
                code="N8N_UNKNOWN_ERROR",
                message=str(e)[:500],
                meta_json={"run_id": run.id},
                correlation_id=run.correlation_id
            )
            logger.error(f"n8n unexpected error for run {run.id}: {e}", exc_info=True)
            raise N8NClientError(str(e))
    
    async def trigger_with_retry(
        self,
        workflow_id: str,
        payload: dict,
        tenant_id: uuid.UUID,
        run: AutomationRun
    ) -> Optional[dict]:
        """
        Trigger n8n workflow with retry logic.
        
        Args:
            workflow_id: n8n workflow ID
            payload: Event payload
            tenant_id: Tenant UUID
            run: AutomationRun record
        
        Returns:
            n8n response or None if all retries failed
        """
        tenant_settings = self.get_tenant_automation_settings(tenant_id)
        
        max_retries = self.max_retries
        if tenant_settings and not tenant_settings.enable_auto_retry:
            max_retries = 0
        elif tenant_settings:
            max_retries = tenant_settings.max_retries
        
        last_error = None
        
        for attempt in range(max_retries + 1):
            try:
                if attempt > 0:
                    # Exponential backoff: 1s, 2s, 4s, ...
                    wait_time = 2 ** (attempt - 1)
                    logger.info(f"Retry attempt {attempt} for run {run.id} after {wait_time}s")
                    await asyncio.sleep(wait_time)
                    run.retry_count = attempt
                    self.db.commit()
                
                return await self.trigger_workflow(workflow_id, payload, tenant_id, run)
            
            except (N8NTimeoutError, N8NConnectionError) as e:
                last_error = e
                if attempt < max_retries:
                    logger.warning(f"Retryable error on attempt {attempt + 1}: {e}")
                    continue
                raise
            
            except N8NClientError:
                # Non-retryable errors (e.g., 4xx responses)
                raise
        
        return None
    
    async def trigger_incoming_message(
        self,
        tenant_id: uuid.UUID,
        from_number: str,
        to_number: str,
        text: str,
        message_id: str,
        timestamp: str,
        channel: str = AutomationChannel.WHATSAPP.value,
        correlation_id: Optional[str] = None,
        contact_name: Optional[str] = None,
        raw_payload: Optional[dict] = None,
        extra_data: Optional[dict] = None
    ) -> Optional[AutomationRun]:
        """
        Main entry point for triggering n8n on incoming messages.
        
        This method:
        1. Checks if n8n is enabled for tenant
        2. Gets the appropriate workflow ID
        3. Creates an automation run record (with idempotency check)
        4. Builds the payload
        5. Triggers n8n with retries
        
        Idempotency:
        - If the same tenant_id + message_id was already processed, returns the existing run
        - Does NOT re-trigger n8n for duplicate messages
        
        Args:
            tenant_id: Tenant UUID
            from_number: Sender phone number
            to_number: Recipient phone number (your WhatsApp number)
            text: Message text
            message_id: External message ID
            timestamp: Message timestamp (ISO format or Unix)
            channel: Channel type
            contact_name: Optional contact name
            raw_payload: Optional raw webhook payload
            extra_data: Optional extra data
        
        Returns:
            AutomationRun record or None if n8n not enabled
        """
        # Check if n8n should be used
        if not self.should_use_n8n(tenant_id):
            logger.debug(f"n8n not enabled for tenant {tenant_id}")
            return None
        
        # Get workflow ID
        workflow_id = self.get_workflow_id(tenant_id, channel)
        if not workflow_id:
            logger.warning(f"No workflow configured for tenant {tenant_id}, channel {channel}")
            return None
        
        # Create automation run (with idempotency check)
        run, is_new = self.create_automation_run(
            tenant_id=tenant_id,
            channel=channel,
            from_number=from_number,
            to_number=to_number,
            message_id=message_id,
            message_content=text,
            workflow_id=workflow_id,
            correlation_id=correlation_id
        )
        
        # If duplicate, return existing run without triggering n8n again
        if not is_new:
            logger.info(
                f"Skipping n8n trigger for duplicate message: "
                f"tenant={tenant_id}, message_id={message_id}, run_id={run.id}"
            )
            return run
        
        # Build payload
        payload = self.build_incoming_message_payload(
            tenant_id=tenant_id,
            channel=channel,
            from_number=from_number,
            to_number=to_number,
            text=text,
            message_id=message_id,
            timestamp=timestamp,
            run_id=str(run.id),
            correlation_id=correlation_id,
            contact_name=contact_name,
            raw_payload=raw_payload,
            extra_data=extra_data
        )
        
        # Trigger workflow (fire and forget - don't block webhook response)
        try:
            await self.trigger_with_retry(workflow_id, payload, tenant_id, run)
        except N8NClientError as e:
            logger.error(f"Failed to trigger n8n workflow: {e}")
            # Run is already marked as failed in trigger methods
        
        return run
    
    def update_run_status(
        self,
        run_id: str,
        status: AutomationRunStatus,
        error_message: Optional[str] = None,
        response_payload: Optional[dict] = None
    ) -> Optional[AutomationRun]:
        """
        Update the status of an automation run.
        
        Called by the callback endpoint when n8n reports completion.
        """
        run = self.db.query(AutomationRun).filter(
            AutomationRun.id == run_id
        ).first()
        
        if not run:
            logger.warning(f"Automation run {run_id} not found")
            return None
        
        if status == AutomationRunStatus.SUCCESS:
            run.mark_success(response_payload)
        elif status == AutomationRunStatus.FAILED:
            run.mark_failed(error_message or "Unknown error", response_payload)
        else:
            run.status = status.value
            run.updated_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(run)
        
        return run


def get_n8n_client(db: Session) -> N8NClient:
    """Factory function to create N8NClient instance."""
    return N8NClient(db)


async def trigger_n8n_in_background(
    tenant_id: uuid.UUID,
    from_number: str,
    to_number: str,
    text: str,
    message_id: str,
    timestamp: str,
    channel: str = AutomationChannel.WHATSAPP.value,
    correlation_id: Optional[str] = None,
    contact_name: Optional[str] = None,
    raw_payload: Optional[dict] = None,
    extra_data: Optional[dict] = None
) -> None:
    """
    Trigger n8n workflow in background with its own DB session.
    
    This function is designed to be called from FastAPI's BackgroundTasks
    and creates its own database session to avoid session-related issues.
    
    This ensures:
    1. The webhook returns HTTP 200 immediately
    2. n8n calls don't block the response
    3. Retries happen in background
    4. DB session is properly managed
    
    Args:
        tenant_id: Tenant UUID
        from_number: Sender phone number
        to_number: Recipient phone number
        text: Message text
        message_id: External message ID
        timestamp: Message timestamp
        channel: Channel type
        contact_name: Optional contact name
        raw_payload: Optional raw webhook payload
        extra_data: Optional extra data
    """
    from app.db.session import SessionLocal
    
    # Create a fresh DB session for this background task
    db = SessionLocal()
    try:
        client = N8NClient(db)
        
        await client.trigger_incoming_message(
            tenant_id=tenant_id,
            from_number=from_number,
            to_number=to_number,
            text=text,
            message_id=message_id,
            timestamp=timestamp,
            channel=channel,
            correlation_id=correlation_id,
            contact_name=contact_name,
            raw_payload=raw_payload,
            extra_data=extra_data
        )
    except Exception as e:
        logger.error(
            f"Background n8n trigger failed: tenant={tenant_id}, "
            f"message_id={message_id}, error={e}",
            exc_info=True
        )
    finally:
        db.close()
