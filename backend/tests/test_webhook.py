"""
Tests for WhatsApp webhook verification and event handling.
"""

import pytest
import hmac
import hashlib
from unittest.mock import Mock, patch, AsyncMock

# Test webhook signature verification
class TestWebhookSignatureVerification:
    """Tests for Meta webhook signature verification."""
    
    def test_valid_signature(self):
        """Test that valid signatures are accepted."""
        from app.services.meta_api import MetaAPIService
        
        service = MetaAPIService()
        service.app_secret = "test_secret"
        
        payload = b'{"test": "data"}'
        expected_sig = hmac.new(
            b"test_secret",
            payload,
            hashlib.sha256
        ).hexdigest()
        
        signature = f"sha256={expected_sig}"
        
        assert service.verify_webhook_signature(payload, signature) == True
    
    def test_invalid_signature(self):
        """Test that invalid signatures are rejected."""
        from app.services.meta_api import MetaAPIService
        
        service = MetaAPIService()
        service.app_secret = "test_secret"
        
        payload = b'{"test": "data"}'
        signature = "sha256=invalid_signature"
        
        assert service.verify_webhook_signature(payload, signature) == False
    
    def test_missing_signature_prefix(self):
        """Test that signatures without sha256= prefix are rejected."""
        from app.services.meta_api import MetaAPIService
        
        service = MetaAPIService()
        service.app_secret = "test_secret"
        
        payload = b'{"test": "data"}'
        signature = "just_a_hash"
        
        assert service.verify_webhook_signature(payload, signature) == False
    
    def test_empty_signature(self):
        """Test that empty signatures are rejected."""
        from app.services.meta_api import MetaAPIService
        
        service = MetaAPIService()
        service.app_secret = "test_secret"
        
        payload = b'{"test": "data"}'
        
        assert service.verify_webhook_signature(payload, "") == False
        assert service.verify_webhook_signature(payload, None) == False


class TestVerifyTokenGeneration:
    """Tests for verify token generation."""
    
    def test_generate_unique_tokens(self):
        """Test that generated tokens are unique."""
        from app.services.meta_api import MetaAPIService
        
        service = MetaAPIService()
        
        tokens = [service.generate_verify_token() for _ in range(100)]
        
        # All tokens should be unique
        assert len(tokens) == len(set(tokens))
    
    def test_token_length(self):
        """Test that generated tokens have sufficient length."""
        from app.services.meta_api import MetaAPIService
        
        service = MetaAPIService()
        
        token = service.generate_verify_token()
        
        # URL-safe base64 of 32 bytes = ~43 characters
        assert len(token) >= 40


class TestEncryption:
    """Tests for token encryption and decryption."""
    
    def test_encrypt_decrypt_roundtrip(self):
        """Test that encryption and decryption work correctly."""
        from app.core.encryption import EncryptionService
        
        service = EncryptionService()
        
        original = "test_access_token_123"
        encrypted = service.encrypt(original)
        decrypted = service.decrypt(encrypted)
        
        assert decrypted == original
        assert encrypted != original  # Should be different
    
    def test_encrypt_empty_string(self):
        """Test encryption of empty string."""
        from app.core.encryption import EncryptionService
        
        service = EncryptionService()
        
        assert service.encrypt("") == ""
        assert service.decrypt("") is None
    
    def test_decrypt_invalid_ciphertext(self):
        """Test decryption of invalid ciphertext."""
        from app.core.encryption import EncryptionService
        
        service = EncryptionService()
        
        assert service.decrypt("invalid_ciphertext") is None
    
    def test_different_keys_produce_different_ciphertext(self):
        """Test that different keys produce different ciphertext."""
        from app.core.encryption import EncryptionService, generate_encryption_key
        
        key1 = generate_encryption_key()
        key2 = generate_encryption_key()
        
        service1 = EncryptionService(key1)
        service2 = EncryptionService(key2)
        
        original = "test_token"
        encrypted1 = service1.encrypt(original)
        encrypted2 = service2.encrypt(original)
        
        assert encrypted1 != encrypted2


class TestOAuthURLGeneration:
    """Tests for OAuth URL generation."""
    
    def test_oauth_url_contains_required_params(self):
        """Test that OAuth URL contains all required parameters."""
        from app.services.meta_api import MetaAPIService
        from app.core.config import settings
        
        service = MetaAPIService()
        old_config_id = getattr(settings, "META_CONFIG_ID", "")
        old_backend_url = getattr(settings, "BACKEND_URL", "")
        old_webhook_public_url = getattr(settings, "WEBHOOK_PUBLIC_URL", "")
        try:
            settings.META_CONFIG_ID = "123456"
            settings.BACKEND_URL = "https://svontai.test"
            settings.WEBHOOK_PUBLIC_URL = "https://svontai.test"
            service.app_id = "123456789"
            service.app_secret = "test_secret"
            service.redirect_uri = "https://svontai.test/api/onboarding/whatsapp/callback"

            url = service.get_oauth_url("test_state")

            assert "client_id=123456789" in url
            assert "redirect_uri=https%3A%2F%2Fsvontai.test%2Fapi%2Fonboarding%2Fwhatsapp%2Fcallback" in url
            assert "state=test_state" in url
            assert "response_type=code" in url
            assert "config_id=123456" in url
            assert "whatsapp_business_management" in url
            assert "whatsapp_business_messaging" in url
        finally:
            settings.META_CONFIG_ID = old_config_id
            settings.BACKEND_URL = old_backend_url
            settings.WEBHOOK_PUBLIC_URL = old_webhook_public_url


class TestOnboardingSteps:
    """Tests for onboarding step definitions."""
    
    def test_all_steps_have_required_fields(self):
        """Test that all onboarding steps have required fields."""
        from app.models.onboarding import WHATSAPP_ONBOARDING_STEPS
        
        required_fields = ["step_key", "step_order", "step_name", "step_description"]
        
        for step in WHATSAPP_ONBOARDING_STEPS:
            for field in required_fields:
                assert field in step, f"Step missing field: {field}"
    
    def test_steps_are_ordered(self):
        """Test that steps have sequential order."""
        from app.models.onboarding import WHATSAPP_ONBOARDING_STEPS
        
        orders = [step["step_order"] for step in WHATSAPP_ONBOARDING_STEPS]
        
        assert orders == sorted(orders), "Steps should be in order"
        assert orders == list(range(1, len(orders) + 1)), "Orders should be sequential from 1"
    
    def test_step_keys_are_unique(self):
        """Test that step keys are unique."""
        from app.models.onboarding import WHATSAPP_ONBOARDING_STEPS
        
        keys = [step["step_key"] for step in WHATSAPP_ONBOARDING_STEPS]
        
        assert len(keys) == len(set(keys)), "Step keys should be unique"


# Mock tests for API calls (integration test stubs)
class TestMetaAPIIntegration:
    """Integration test stubs for Meta Graph API calls."""
    
    @pytest.mark.asyncio
    async def test_token_exchange_mock(self):
        """Mock test for token exchange."""
        from app.services.meta_api import MetaAPIService
        from app.core.config import settings
        
        service = MetaAPIService()
        old_config_id = getattr(settings, "META_CONFIG_ID", "")
        old_backend_url = getattr(settings, "BACKEND_URL", "")
        old_webhook_public_url = getattr(settings, "WEBHOOK_PUBLIC_URL", "")
        try:
            settings.META_CONFIG_ID = "123456"
            settings.BACKEND_URL = "https://svontai.test"
            settings.WEBHOOK_PUBLIC_URL = "https://svontai.test"
            service.app_id = "123456789"
            service.app_secret = "test_secret"
            service.redirect_uri = "https://svontai.test/api/onboarding/whatsapp/callback"
        
            with patch('httpx.AsyncClient') as mock_client:
                mock_response = Mock()
                mock_response.json.return_value = {
                    "access_token": "test_token",
                    "token_type": "bearer",
                    "expires_in": 3600
                }
                
                mock_client_instance = AsyncMock()
                mock_client_instance.get.return_value = mock_response
                mock_client.return_value.__aenter__.return_value = mock_client_instance
                
                result = await service.exchange_code_for_token("test_code")
                
                assert result["access_token"] == "test_token"
        finally:
            settings.META_CONFIG_ID = old_config_id
            settings.BACKEND_URL = old_backend_url
            settings.WEBHOOK_PUBLIC_URL = old_webhook_public_url
    
    @pytest.mark.asyncio
    async def test_get_phone_numbers_mock(self):
        """Mock test for getting phone numbers."""
        from app.services.meta_api import MetaAPIService
        
        service = MetaAPIService()
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = Mock()
            mock_response.json.return_value = {
                "data": [
                    {
                        "id": "123456789",
                        "display_phone_number": "+90 555 123 4567",
                        "verified_name": "Test Business",
                        "quality_rating": "GREEN",
                        "status": "CONNECTED"
                    }
                ]
            }
            
            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_client_instance
            
            result = await service.get_phone_numbers("test_token", "test_waba_id")
            
            assert len(result) == 1
            assert result[0]["id"] == "123456789"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
