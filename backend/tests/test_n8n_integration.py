"""
Tests for n8n integration features:
- Idempotency (duplicate message handling)
- Webhook timeout protection
- Production secret validation
"""

import pytest
import uuid
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime
from app.core.time import utc_now_naive
import time


def _prod_real_service_settings(**overrides):
    data = {
        "ENVIRONMENT": "prod",
        "JWT_SECRET_KEY": "secure-jwt-key-32-chars-minimum!",
        "VOICE_GATEWAY_TO_SVONTAI_SECRET": "secure-voice-gateway-secret!",
        "OPENAI_API_KEY": "sk-prod-test-key",
        "WEBHOOK_USERNAME": "prod-webhook-user",
        "WEBHOOK_PASSWORD": "prod-webhook-password",
        "EMAIL_ENABLED": True,
        "EMAIL_PROVIDER": "resend",
        "RESEND_API_KEY": "re_live_test",
        "BILLING_MODE": "stripe",
        "PAYMENTS_ENABLED": True,
        "STRIPE_SECRET_KEY": "sk_live_test",
        "STRIPE_WEBHOOK_SECRET": "whsec_live_test",
        "STRIPE_SUCCESS_URL": "https://app.svontai.com/billing/success",
        "STRIPE_CANCEL_URL": "https://app.svontai.com/billing/cancel",
        "STRIPE_PORTAL_RETURN_URL": "https://app.svontai.com/dashboard/billing",
        "STRIPE_PRICE_IDS": {"pro": {"monthly": "price_live_pro"}},
        "USE_N8N": True,
        "N8N_BASE_URL": "https://n8n.svontai.com",
        "N8N_INCOMING_WORKFLOW_ID": "incoming-prod",
        "SVONTAI_TO_N8N_SECRET": "secure-svontai-to-n8n-secret!",
        "N8N_TO_SVONTAI_SECRET": "secure-n8n-to-svontai-secret!",
        "N8N_ERROR_WEBHOOK_SECRET": "secure-n8n-error-webhook-secret!",
        "ARTIFACT_STORAGE_PROVIDER": "supabase",
        "SUPABASE_URL": "https://project.supabase.co",
        "SUPABASE_SERVICE_ROLE_KEY": "supabase-service-role-key",
        "SUPABASE_STORAGE_BUCKET": "svontai-artifacts",
        "ARTIFACT_SIGNING_SECRET": "secure-artifact-signing-secret!",
        "RATE_LIMIT_BACKEND": "redis",
        "REDIS_URL": "redis://redis.internal:6379/0",
        "SENTRY_DSN": "https://public@example.ingest.sentry.io/1",
        "WEBHOOK_PUBLIC_URL": "https://api.svontai.com",
        "BACKEND_URL": "https://api.svontai.com",
        "FRONTEND_URL": "https://app.svontai.com",
    }
    data.update(overrides)
    return data


class TestIdempotency:
    """Test idempotency / duplicate message handling."""
    
    def test_idempotent_statuses_defined(self):
        """Test that idempotent statuses are correctly defined."""
        from app.services.n8n_client import IDEMPOTENT_STATUSES
        from app.models.automation import AutomationRunStatus
        
        # These statuses should prevent re-triggering
        assert AutomationRunStatus.RECEIVED.value in IDEMPOTENT_STATUSES
        assert AutomationRunStatus.RUNNING.value in IDEMPOTENT_STATUSES
        assert AutomationRunStatus.SUCCESS.value in IDEMPOTENT_STATUSES
        
        # Failed status should NOT be in idempotent statuses (allow retry)
        assert AutomationRunStatus.FAILED.value not in IDEMPOTENT_STATUSES
        assert AutomationRunStatus.TIMEOUT.value not in IDEMPOTENT_STATUSES
    
    def test_create_automation_run_returns_tuple(self):
        """Test that create_automation_run returns (run, is_new) tuple."""
        from app.services.n8n_client import N8NClient
        
        # Mock DB session
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        client = N8NClient(mock_db)
        
        # Mock the methods that interact with DB
        with patch.object(client, 'check_duplicate_message', return_value=(False, None)):
            # Simulate successful add
            mock_db.commit = MagicMock()
            mock_db.add = MagicMock()
            mock_db.refresh = MagicMock()
            
            run, is_new = client.create_automation_run(
                tenant_id=uuid.uuid4(),
                channel="whatsapp",
                from_number="+1234567890",
                to_number="+0987654321",
                message_id="wamid.test123",
                message_content="Hello",
                workflow_id="test-workflow"
            )
            
            # Verify it's a new run
            assert is_new is True
            assert run is not None
    
    def test_duplicate_detection_logic(self):
        """Test duplicate message detection logic."""
        from app.services.n8n_client import N8NClient
        from app.models.automation import AutomationRun, AutomationRunStatus
        
        mock_db = MagicMock()
        
        # Create a mock existing run
        existing_run = MagicMock(spec=AutomationRun)
        existing_run.id = str(uuid.uuid4())
        existing_run.status = AutomationRunStatus.RECEIVED.value
        
        # Mock query to return existing run
        mock_db.query.return_value.filter.return_value.first.return_value = existing_run
        
        client = N8NClient(mock_db)
        
        is_dup, found_run = client.check_duplicate_message(
            tenant_id=uuid.uuid4(),
            message_id="wamid.existing"
        )
        
        assert is_dup is True
        assert found_run == existing_run
    
    def test_null_message_id_skips_duplicate_check(self):
        """Test that null message_id skips duplicate check."""
        from app.services.n8n_client import N8NClient
        
        mock_db = MagicMock()
        client = N8NClient(mock_db)
        
        is_dup, found_run = client.check_duplicate_message(
            tenant_id=uuid.uuid4(),
            message_id=None  # null message_id
        )
        
        # Should return not duplicate without querying DB
        assert is_dup is False
        assert found_run is None
        mock_db.query.assert_not_called()


class TestWebhookTimeout:
    """Test webhook timeout protection."""
    
    @pytest.mark.asyncio
    async def test_background_task_creates_fresh_session(self):
        """Test that background task creates its own DB session."""
        with patch('app.db.session.SessionLocal') as mock_session_local:
            mock_db = MagicMock()
            mock_session_local.return_value = mock_db
            
            # Mock the N8NClient
            with patch('app.services.n8n_client.N8NClient') as mock_client_class:
                mock_client = MagicMock()
                mock_client.trigger_incoming_message = AsyncMock(return_value=None)
                mock_client_class.return_value = mock_client
                
                from app.services.n8n_client import trigger_n8n_in_background
                
                await trigger_n8n_in_background(
                    tenant_id=uuid.uuid4(),
                    from_number="+1234567890",
                    to_number="+0987654321",
                    text="Test message",
                    message_id="wamid.test",
                    timestamp=utc_now_naive().isoformat()
                )
                
                # Verify SessionLocal was called to create new session
                mock_session_local.assert_called_once()
                
                # Verify session was closed
                mock_db.close.assert_called_once()
    
    def test_webhook_handler_returns_immediately(self):
        """Test that webhook handler patterns allow immediate return."""
        from fastapi import BackgroundTasks
        
        start_time = time.time()
        
        # Create background tasks object
        background_tasks = BackgroundTasks()
        
        # Adding a task should be nearly instant
        async def slow_task():
            await asyncio.sleep(5)
        
        background_tasks.add_task(slow_task)
        
        elapsed = time.time() - start_time
        
        # Adding task should be instant (< 100ms)
        assert elapsed < 0.1, f"Adding background task took {elapsed}s"


def test_webhook_url_normalizes_trailing_slashes(monkeypatch):
    from app.core.config import settings
    from app.services.n8n_client import N8NClient

    monkeypatch.setattr(settings, "N8N_BASE_URL", "https://n8n.example.com/")
    monkeypatch.setattr(settings, "N8N_WEBHOOK_PATH", "/webhook/")
    client = N8NClient(MagicMock())
    client.base_url = settings.N8N_BASE_URL.rstrip("/")
    client.get_tenant_automation_settings = MagicMock(return_value=None)

    assert client.get_webhook_url(
        uuid.uuid4(),
        "/svontai-whatsapp-v2/",
    ) == "https://n8n.example.com/webhook/svontai-whatsapp-v2"


class TestWorkflowResultHandling:
    @pytest.mark.asyncio
    async def test_business_failure_is_not_marked_success(self):
        from app.services.n8n_client import N8NClient

        mock_db = MagicMock()
        run = MagicMock()
        run.id = uuid.uuid4()
        response = MagicMock()
        response.content = b'{"success":false}'
        response.json.return_value = {
            "success": False,
            "executionId": "exec-failed",
            "error": {"message": "provider unavailable", "code": "PROVIDER_DOWN"},
        }
        response.raise_for_status.return_value = None

        http_client = AsyncMock()
        http_client.post.return_value = response
        context = AsyncMock()
        context.__aenter__.return_value = http_client
        context.__aexit__.return_value = None

        service = N8NClient(mock_db)
        with patch.object(service, "get_n8n_url", return_value="https://n8n.example.com"), patch(
            "app.services.n8n_client.httpx.AsyncClient",
            return_value=context,
        ):
            result = await service.trigger_workflow(
                workflow_id="secure-workflow",
                payload={"event": "test"},
                tenant_id=uuid.uuid4(),
                run=run,
            )

        assert result["success"] is False
        run.mark_failed.assert_called_once_with("provider unavailable", response.json.return_value)
        run.mark_success.assert_not_called()


class TestProductionSecretValidation:
    """Test production secret validation."""
    
    def test_insecure_default_secrets_list_exists(self):
        """Test that insecure default secrets list is defined."""
        from app.core.config import INSECURE_DEFAULT_SECRETS
        
        assert isinstance(INSECURE_DEFAULT_SECRETS, list)
        assert len(INSECURE_DEFAULT_SECRETS) > 0
        
        # Verify our known insecure defaults are in the list
        assert "change-this-to-a-secure-random-string-svontai-to-n8n" in INSECURE_DEFAULT_SECRETS
        assert "change-this-to-a-secure-random-string-n8n-to-svontai" in INSECURE_DEFAULT_SECRETS
        assert "your-super-secret-jwt-key-change-in-production" in INSECURE_DEFAULT_SECRETS
    
    def test_insecure_jwt_secret_fails_in_production(self):
        """Test that insecure JWT secret fails in production."""
        from pydantic import ValidationError
        from app.core.config import Settings
        
        with pytest.raises(ValidationError) as exc_info:
            Settings(**_prod_real_service_settings(JWT_SECRET_KEY="your-super-secret-jwt-key-change-in-production"))
        
        # Should mention JWT_SECRET_KEY in error
        error_str = str(exc_info.value)
        assert "JWT_SECRET_KEY" in error_str or "insecure" in error_str.lower()
    
    def test_insecure_n8n_secrets_fail_when_enabled(self):
        """Test that insecure n8n secrets fail in production when n8n enabled."""
        from pydantic import ValidationError
        from app.core.config import Settings
        
        # Test SVONTAI_TO_N8N_SECRET
        with pytest.raises(ValidationError):
            Settings(**_prod_real_service_settings(
                SVONTAI_TO_N8N_SECRET="change-this-to-a-secure-random-string-svontai-to-n8n"
            ))
    
    def test_prod_requires_real_time_external_services(self):
        """Test that production fails when real-time external services are disabled."""
        from pydantic import ValidationError
        from app.core.config import Settings
        
        with pytest.raises(ValidationError) as exc_info:
            Settings(**_prod_real_service_settings(USE_N8N=False))

        assert "USE_N8N=true" in str(exc_info.value)
    
    def test_secure_secrets_work_in_production(self):
        """Test that secure secrets work in production."""
        from app.core.config import Settings
        
        settings = Settings(**_prod_real_service_settings(
            JWT_SECRET_KEY="my-super-secure-jwt-key-for-prod",
        ))
        
        assert settings.ENVIRONMENT == "prod"
        assert settings.USE_N8N is True

    def test_manual_billing_does_not_require_stripe_in_production(self):
        from app.core.config import Settings

        configured = Settings(**_prod_real_service_settings(
            BILLING_MODE="manual",
            PAYMENTS_ENABLED=False,
            STRIPE_SECRET_KEY="",
            STRIPE_WEBHOOK_SECRET="",
            STRIPE_SUCCESS_URL="",
            STRIPE_CANCEL_URL="",
            STRIPE_PORTAL_RETURN_URL="",
            STRIPE_PRICE_IDS={},
        ))

        assert configured.BILLING_MODE == "manual"
        assert configured.PAYMENTS_ENABLED is False

    def test_railway_volume_satisfies_production_storage_requirement(self):
        from app.core.config import Settings

        configured = Settings(**_prod_real_service_settings(
            ARTIFACT_STORAGE_PROVIDER="railway_volume",
            ARTIFACT_STORAGE_LOCAL_BASE_PATH="/app/backend/storage/artifacts",
            RAILWAY_VOLUME_MOUNT_PATH="/app/backend/storage",
            SUPABASE_URL="",
            SUPABASE_SERVICE_ROLE_KEY="",
        ))

        assert configured.ARTIFACT_STORAGE_PROVIDER == "railway_volume"

    def test_production_rejects_local_or_outside_volume_artifact_storage(self):
        from pydantic import ValidationError
        from app.core.config import Settings

        with pytest.raises(ValidationError, match="railway_volume or supabase"):
            Settings(**_prod_real_service_settings(ARTIFACT_STORAGE_PROVIDER="local"))

        with pytest.raises(ValidationError, match="inside RAILWAY_VOLUME_MOUNT_PATH"):
            Settings(**_prod_real_service_settings(
                ARTIFACT_STORAGE_PROVIDER="railway_volume",
                ARTIFACT_STORAGE_LOCAL_BASE_PATH="/tmp/artifacts",
                RAILWAY_VOLUME_MOUNT_PATH="/app/backend/storage",
            ))

    def test_production_worker_delegates_artifact_storage_to_api(self):
        from app.core.config import Settings

        configured = Settings(**_prod_real_service_settings(
            SERVICE_ROLE="worker",
            ARTIFACT_STORAGE_PROVIDER="local",
            ARTIFACT_STORAGE_LOCAL_BASE_PATH="storage/artifacts",
            RAILWAY_VOLUME_MOUNT_PATH="",
            ARTIFACT_SIGNING_SECRET="",
            SUPABASE_URL="",
            SUPABASE_SERVICE_ROLE_KEY="",
        ))

        assert configured.SERVICE_ROLE == "worker"

    def test_gemini_key_satisfies_production_ai_requirement(self):
        from app.core.config import Settings

        configured = Settings(**_prod_real_service_settings(
            AI_PROVIDER="gemini",
            AI_MODEL="gemini-3.1-flash-lite",
            GEMINI_API_KEY="gemini-prod-test-key",
            OPENAI_API_KEY="",
        ))

        assert configured.ai_api_key == "gemini-prod-test-key"
        assert configured.ai_model == "gemini-3.1-flash-lite"
    
    def test_insecure_secrets_allowed_in_dev(self):
        """Test that insecure secrets are allowed in development."""
        from app.core.config import Settings
        
        # Should NOT raise in dev environment
        settings = Settings(
            ENVIRONMENT="dev",
            JWT_SECRET_KEY="your-super-secret-jwt-key-change-in-production"
        )
        
        assert settings.ENVIRONMENT == "dev"


class TestConstantTimeCompare:
    """Test that security-sensitive comparisons use constant-time compare."""
    
    def test_signature_uses_hmac_compare_digest(self):
        """Verify signature verification uses hmac.compare_digest."""
        import inspect
        from app.core.n8n_security import verify_signature
        
        source = inspect.getsource(verify_signature)
        
        assert "hmac.compare_digest" in source, \
            "verify_signature should use hmac.compare_digest for constant-time comparison"
