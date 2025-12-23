"""
Meta Graph API service for WhatsApp Business API integration.
Handles OAuth, token exchange, and WABA management.
"""

import secrets
import httpx
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

from app.core.config import settings


class MetaAPIError(Exception):
    """Custom exception for Meta API errors."""
    
    def __init__(self, message: str, error_code: Optional[str] = None, details: Optional[Dict] = None):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)


class MetaAPIService:
    """Service for interacting with Meta Graph API."""
    
    # API Configuration
    GRAPH_API_VERSION = "v18.0"
    GRAPH_API_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"
    OAUTH_BASE = "https://www.facebook.com/{version}/dialog/oauth"
    
    # Required permissions for WhatsApp Business API
    WHATSAPP_PERMISSIONS = [
        "whatsapp_business_management",
        "whatsapp_business_messaging",
        "business_management"
    ]
    
    def __init__(self):
        """Initialize Meta API service with configuration."""
        self.app_id = getattr(settings, 'META_APP_ID', '')
        self.app_secret = getattr(settings, 'META_APP_SECRET', '')
        self.redirect_uri = getattr(settings, 'META_REDIRECT_URI', '')
        self.api_version = getattr(settings, 'GRAPH_API_VERSION', self.GRAPH_API_VERSION)
        
        # Update base URLs with configured version
        self.graph_base = f"https://graph.facebook.com/{self.api_version}"
    
    def generate_verify_token(self) -> str:
        """
        Generate a secure webhook verify token.
        
        Returns:
            Random URL-safe string.
        """
        return secrets.token_urlsafe(32)
    
    def get_oauth_url(self, state: str) -> str:
        """
        Generate the Meta OAuth authorization URL for Embedded Signup.
        
        Args:
            state: State parameter for CSRF protection (should include tenant info).
            
        Returns:
            Full OAuth URL for redirect.
        """
        params = {
            "client_id": self.app_id,
            "redirect_uri": self.redirect_uri,
            "state": state,
            "scope": ",".join(self.WHATSAPP_PERMISSIONS),
            "response_type": "code",
            # Enable Embedded Signup
            "config_id": getattr(settings, 'META_CONFIG_ID', ''),
        }
        
        # Build URL
        query = "&".join(f"{k}={v}" for k, v in params.items() if v)
        return f"https://www.facebook.com/{self.api_version}/dialog/oauth?{query}"
    
    def get_embedded_signup_config(self, state: str) -> Dict[str, Any]:
        """
        Get configuration for Meta Embedded Signup SDK.
        
        Args:
            state: State parameter for session tracking.
            
        Returns:
            Configuration dict for frontend SDK.
        """
        return {
            "appId": self.app_id,
            "configId": getattr(settings, 'META_CONFIG_ID', ''),
            "redirectUri": self.redirect_uri,
            "state": state,
            "scope": ",".join(self.WHATSAPP_PERMISSIONS),
            "responseType": "code",
            "sdkVersion": self.api_version,
            "featureType": "whatsapp_embedded_signup",
            "sessionInfoVersion": 2,
        }
    
    async def exchange_code_for_token(self, code: str) -> Dict[str, Any]:
        """
        Exchange authorization code for access token.
        
        Args:
            code: Authorization code from OAuth callback.
            
        Returns:
            Dict containing access_token and token metadata.
            
        Raises:
            MetaAPIError: If token exchange fails.
        """
        url = f"{self.graph_base}/oauth/access_token"
        params = {
            "client_id": self.app_id,
            "client_secret": self.app_secret,
            "redirect_uri": self.redirect_uri,
            "code": code,
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            data = response.json()
            
            if "error" in data:
                raise MetaAPIError(
                    message=data["error"].get("message", "Token exchange failed"),
                    error_code=data["error"].get("code"),
                    details=data["error"]
                )
            
            return {
                "access_token": data.get("access_token"),
                "token_type": data.get("token_type", "bearer"),
                "expires_in": data.get("expires_in"),
            }
    
    async def get_long_lived_token(self, short_lived_token: str) -> Dict[str, Any]:
        """
        Exchange short-lived token for long-lived token.
        
        Args:
            short_lived_token: Short-lived access token.
            
        Returns:
            Dict containing long-lived access_token.
            
        Raises:
            MetaAPIError: If exchange fails.
        """
        url = f"{self.graph_base}/oauth/access_token"
        params = {
            "grant_type": "fb_exchange_token",
            "client_id": self.app_id,
            "client_secret": self.app_secret,
            "fb_exchange_token": short_lived_token,
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            data = response.json()
            
            if "error" in data:
                raise MetaAPIError(
                    message=data["error"].get("message", "Long-lived token exchange failed"),
                    error_code=data["error"].get("code"),
                    details=data["error"]
                )
            
            return {
                "access_token": data.get("access_token"),
                "token_type": data.get("token_type", "bearer"),
                "expires_in": data.get("expires_in", 5184000),  # ~60 days default
            }
    
    async def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """
        Get basic user info from access token.
        
        Args:
            access_token: Valid access token.
            
        Returns:
            User info dict.
        """
        url = f"{self.graph_base}/me"
        params = {
            "access_token": access_token,
            "fields": "id,name,email"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            data = response.json()
            
            if "error" in data:
                raise MetaAPIError(
                    message=data["error"].get("message", "Failed to get user info"),
                    error_code=data["error"].get("code"),
                    details=data["error"]
                )
            
            return data
    
    async def get_whatsapp_business_accounts(self, access_token: str, business_id: Optional[str] = None) -> list:
        """
        Get WhatsApp Business Accounts accessible with the token.
        
        Args:
            access_token: Valid access token.
            business_id: Optional specific business ID.
            
        Returns:
            List of WABA objects.
        """
        # First get businesses
        if not business_id:
            businesses = await self._get_businesses(access_token)
            if not businesses:
                return []
            business_id = businesses[0].get("id")
        
        url = f"{self.graph_base}/{business_id}/owned_whatsapp_business_accounts"
        params = {
            "access_token": access_token,
            "fields": "id,name,currency,timezone_id,message_template_namespace"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            data = response.json()
            
            if "error" in data:
                raise MetaAPIError(
                    message=data["error"].get("message", "Failed to get WABAs"),
                    error_code=data["error"].get("code"),
                    details=data["error"]
                )
            
            return data.get("data", [])
    
    async def _get_businesses(self, access_token: str) -> list:
        """Get businesses accessible with token."""
        url = f"{self.graph_base}/me/businesses"
        params = {
            "access_token": access_token,
            "fields": "id,name"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            data = response.json()
            
            if "error" in data:
                return []
            
            return data.get("data", [])
    
    async def get_phone_numbers(self, access_token: str, waba_id: str) -> list:
        """
        Get phone numbers for a WhatsApp Business Account.
        
        Args:
            access_token: Valid access token.
            waba_id: WhatsApp Business Account ID.
            
        Returns:
            List of phone number objects.
        """
        url = f"{self.graph_base}/{waba_id}/phone_numbers"
        params = {
            "access_token": access_token,
            "fields": "id,display_phone_number,verified_name,quality_rating,status"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            data = response.json()
            
            if "error" in data:
                raise MetaAPIError(
                    message=data["error"].get("message", "Failed to get phone numbers"),
                    error_code=data["error"].get("code"),
                    details=data["error"]
                )
            
            return data.get("data", [])
    
    async def subscribe_to_webhooks(self, access_token: str, waba_id: str) -> bool:
        """
        Subscribe WABA to receive webhook events.
        
        Args:
            access_token: Valid access token.
            waba_id: WhatsApp Business Account ID.
            
        Returns:
            True if subscription successful.
        """
        url = f"{self.graph_base}/{waba_id}/subscribed_apps"
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                params={"access_token": access_token}
            )
            data = response.json()
            
            if "error" in data:
                raise MetaAPIError(
                    message=data["error"].get("message", "Failed to subscribe to webhooks"),
                    error_code=data["error"].get("code"),
                    details=data["error"]
                )
            
            return data.get("success", False)
    
    async def register_phone_number(self, access_token: str, phone_number_id: str, pin: str = "000000") -> bool:
        """
        Register a phone number for use with WhatsApp Business API.
        
        Args:
            access_token: Valid access token.
            phone_number_id: Phone Number ID.
            pin: 6-digit PIN for 2FA.
            
        Returns:
            True if registration successful.
        """
        url = f"{self.graph_base}/{phone_number_id}/register"
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                params={"access_token": access_token},
                json={
                    "messaging_product": "whatsapp",
                    "pin": pin
                }
            )
            data = response.json()
            
            if "error" in data:
                raise MetaAPIError(
                    message=data["error"].get("message", "Failed to register phone number"),
                    error_code=data["error"].get("code"),
                    details=data["error"]
                )
            
            return data.get("success", False)
    
    async def send_text_message(
        self, 
        access_token: str, 
        phone_number_id: str, 
        to: str, 
        text: str
    ) -> Dict[str, Any]:
        """
        Send a text message via WhatsApp.
        
        Args:
            access_token: Valid access token.
            phone_number_id: Phone Number ID to send from.
            to: Recipient phone number (with country code).
            text: Message text.
            
        Returns:
            Message response with message_id.
        """
        url = f"{self.graph_base}/{phone_number_id}/messages"
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                },
                json={
                    "messaging_product": "whatsapp",
                    "recipient_type": "individual",
                    "to": to,
                    "type": "text",
                    "text": {"body": text}
                }
            )
            data = response.json()
            
            if "error" in data:
                raise MetaAPIError(
                    message=data["error"].get("message", "Failed to send message"),
                    error_code=data["error"].get("code"),
                    details=data["error"]
                )
            
            return data
    
    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """
        Verify webhook payload signature from Meta.
        
        Args:
            payload: Raw request body.
            signature: X-Hub-Signature-256 header value.
            
        Returns:
            True if signature is valid.
        """
        import hmac
        import hashlib
        
        if not signature or not signature.startswith("sha256="):
            return False
        
        expected_signature = signature[7:]  # Remove "sha256=" prefix
        
        computed = hmac.new(
            self.app_secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(computed, expected_signature)


# Singleton instance
meta_api_service = MetaAPIService()

