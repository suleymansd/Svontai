"""
WhatsApp Cloud API Service for sending and receiving messages.
"""

import httpx
from typing import Any

from app.core.config import settings
from app.models.whatsapp import WhatsAppIntegration


class WhatsAppService:
    """Service for WhatsApp Cloud API interactions."""
    
    def __init__(self):
        """Initialize the HTTP client."""
        self.base_url = settings.WHATSAPP_BASE_URL
    
    async def send_message(
        self,
        integration: WhatsAppIntegration,
        recipient_phone: str,
        message: str
    ) -> dict[str, Any]:
        """
        Send a text message via WhatsApp Cloud API.
        
        Args:
            integration: WhatsApp integration with credentials.
            recipient_phone: The recipient's phone number (with country code).
            message: The message text to send.
        
        Returns:
            The API response data.
        """
        url = f"{self.base_url}/{integration.whatsapp_phone_number_id}/messages"
        
        headers = {
            "Authorization": f"Bearer {integration.access_token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient_phone,
            "type": "text",
            "text": {
                "preview_url": False,
                "body": message
            }
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()
    
    async def send_template_message(
        self,
        integration: WhatsAppIntegration,
        recipient_phone: str,
        template_name: str,
        language_code: str = "tr",
        components: list[dict] | None = None
    ) -> dict[str, Any]:
        """
        Send a template message via WhatsApp Cloud API.
        
        Args:
            integration: WhatsApp integration with credentials.
            recipient_phone: The recipient's phone number.
            template_name: The name of the approved template.
            language_code: The language code for the template.
            components: Optional template components for parameters.
        
        Returns:
            The API response data.
        """
        url = f"{self.base_url}/{integration.whatsapp_phone_number_id}/messages"
        
        headers = {
            "Authorization": f"Bearer {integration.access_token}",
            "Content-Type": "application/json"
        }
        
        template_data = {
            "name": template_name,
            "language": {"code": language_code}
        }
        
        if components:
            template_data["components"] = components
        
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient_phone,
            "type": "template",
            "template": template_data
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()
    
    def parse_incoming_message(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        """
        Parse an incoming WhatsApp webhook payload.
        
        Args:
            payload: The raw webhook payload from Meta.
        
        Returns:
            Parsed message data or None if not a valid message.
        """
        try:
            entry = payload.get("entry", [])
            if not entry:
                return None
            
            changes = entry[0].get("changes", [])
            if not changes:
                return None
            
            value = changes[0].get("value", {})
            
            # Check if this is a message event
            messages = value.get("messages", [])
            if not messages:
                return None
            
            message = messages[0]
            
            # Get contact info
            contacts = value.get("contacts", [])
            contact = contacts[0] if contacts else {}
            
            # Get phone number ID
            metadata = value.get("metadata", {})
            phone_number_id = metadata.get("phone_number_id")
            
            return {
                "phone_number_id": phone_number_id,
                "from": message.get("from"),  # Sender's phone number
                "message_id": message.get("id"),
                "timestamp": message.get("timestamp"),
                "type": message.get("type"),
                "text": message.get("text", {}).get("body", ""),
                "contact_name": contact.get("profile", {}).get("name", ""),
                "raw_payload": payload
            }
        
        except (KeyError, IndexError) as e:
            print(f"Error parsing WhatsApp message: {e}")
            return None
    
    def verify_webhook(self, mode: str, token: str, challenge: str, verify_token: str) -> str | None:
        """
        Verify the webhook subscription from Meta.
        
        Args:
            mode: The hub.mode parameter.
            token: The hub.verify_token parameter.
            challenge: The hub.challenge parameter.
            verify_token: The expected verify token.
        
        Returns:
            The challenge string if verification passes, None otherwise.
        """
        if mode == "subscribe" and token == verify_token:
            return challenge
        return None


# Singleton instance
whatsapp_service = WhatsAppService()

