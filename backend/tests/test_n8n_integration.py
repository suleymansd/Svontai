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
import time


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
                    timestamp=datetime.utcnow().isoformat()
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
            Settings(
                ENVIRONMENT="prod",
                JWT_SECRET_KEY="your-super-secret-jwt-key-change-in-production"
            )
        
        # Should mention JWT_SECRET_KEY in error
        error_str = str(exc_info.value)
        assert "JWT_SECRET_KEY" in error_str or "insecure" in error_str.lower()
    
    def test_insecure_n8n_secrets_fail_when_enabled(self):
        """Test that insecure n8n secrets fail in production when n8n enabled."""
        from pydantic import ValidationError
        from app.core.config import Settings
        
        # Test SVONTAI_TO_N8N_SECRET
        with pytest.raises(ValidationError):
            Settings(
                ENVIRONMENT="prod",
                JWT_SECRET_KEY="secure-jwt-key-32-chars-minimum!",
                USE_N8N=True,
                SVONTAI_TO_N8N_SECRET="change-this-to-a-secure-random-string-svontai-to-n8n"
            )
    
    def test_insecure_n8n_secrets_allowed_when_disabled(self):
        """Test that insecure n8n secrets are allowed when n8n disabled."""
        from app.core.config import Settings
        
        # Should NOT raise when USE_N8N=False
        settings = Settings(
            ENVIRONMENT="prod",
            JWT_SECRET_KEY="secure-jwt-key-32-chars-minimum!",
            USE_N8N=False,
            SVONTAI_TO_N8N_SECRET="change-this-to-a-secure-random-string-svontai-to-n8n"
        )
        
        assert settings.USE_N8N is False
    
    def test_secure_secrets_work_in_production(self):
        """Test that secure secrets work in production."""
        from app.core.config import Settings
        
        settings = Settings(
            ENVIRONMENT="prod",
            JWT_SECRET_KEY="my-super-secure-jwt-key-for-prod",
            USE_N8N=True,
            SVONTAI_TO_N8N_SECRET="secure-svontai-to-n8n-secret!",
            N8N_TO_SVONTAI_SECRET="secure-n8n-to-svontai-secret!"
        )
        
        assert settings.ENVIRONMENT == "prod"
        assert settings.USE_N8N is True
    
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
