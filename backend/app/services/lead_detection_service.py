"""
Lead detection service for automatic lead capture from conversations.
"""

import re
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models.lead import Lead, LeadStatus, LeadSource
from app.models.conversation import Conversation


class LeadDetectionService:
    """Service for detecting and capturing leads from conversations."""
    
    # Regex patterns for detecting contact information
    EMAIL_PATTERN = re.compile(
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    )
    
    # Turkish phone patterns
    PHONE_PATTERNS = [
        re.compile(r'\b(?:\+90|0090|90)?[\s.-]?(?:5\d{2})[\s.-]?(\d{3})[\s.-]?(\d{2})[\s.-]?(\d{2})\b'),  # Mobile
        re.compile(r'\b(?:\+90|0090|90)?[\s.-]?(?:2\d{2}|3\d{2}|4\d{2})[\s.-]?(\d{3})[\s.-]?(\d{2})[\s.-]?(\d{2})\b'),  # Landline
        re.compile(r'\b0?\s?5\d{2}\s?\d{3}\s?\d{2}\s?\d{2}\b'),  # Simplified mobile
        re.compile(r'\b\d{10,11}\b')  # Raw numbers
    ]
    
    # Name patterns (basic detection)
    NAME_PATTERNS = [
        re.compile(r'(?:benim?\s+(?:adım?|ismim?))\s+([A-ZÇĞİÖŞÜa-zçğıöşü]+(?:\s+[A-ZÇĞİÖŞÜa-zçğıöşü]+)?)', re.IGNORECASE),
        re.compile(r'(?:ben)\s+([A-ZÇĞİÖŞÜ][a-zçğıöşü]+(?:\s+[A-ZÇĞİÖŞÜ][a-zçğıöşü]+)?)', re.IGNORECASE),
        re.compile(r'(?:my\s+name\s+is)\s+([A-Za-z]+(?:\s+[A-Za-z]+)?)', re.IGNORECASE)
    ]
    
    def __init__(self, db: Session):
        self.db = db
    
    def detect_lead_info(self, text: str) -> dict:
        """
        Detect lead information from text.
        
        Returns dict with detected fields and confidence scores.
        """
        detected = {
            "email": None,
            "phone": None,
            "name": None,
            "confidence": 0.0,
            "detected_fields": []
        }
        
        # Detect email
        email_match = self.EMAIL_PATTERN.search(text)
        if email_match:
            detected["email"] = email_match.group()
            detected["detected_fields"].append("email")
            detected["confidence"] += 0.4
        
        # Detect phone
        for pattern in self.PHONE_PATTERNS:
            phone_match = pattern.search(text)
            if phone_match:
                # Clean phone number
                phone = re.sub(r'[\s.-]', '', phone_match.group())
                if len(phone) >= 10:
                    detected["phone"] = phone
                    detected["detected_fields"].append("phone")
                    detected["confidence"] += 0.3
                    break
        
        # Detect name
        for pattern in self.NAME_PATTERNS:
            name_match = pattern.search(text)
            if name_match:
                detected["name"] = name_match.group(1).strip()
                detected["detected_fields"].append("name")
                detected["confidence"] += 0.3
                break
        
        # Cap confidence at 1.0
        detected["confidence"] = min(detected["confidence"], 1.0)
        
        return detected
    
    def process_message(
        self,
        conversation: Conversation,
        message_content: str,
        tenant_id: uuid.UUID
    ) -> Optional[Lead]:
        """
        Process a message and create/update lead if contact info is detected.
        
        Returns Lead if created/updated, None otherwise.
        """
        detected = self.detect_lead_info(message_content)
        
        # Only create lead if we have significant contact info
        if not detected["detected_fields"]:
            return None
        
        # Check if lead already exists for this conversation
        existing_lead = self.db.query(Lead).filter(
            Lead.conversation_id == conversation.id,
            Lead.is_deleted == False
        ).first()
        
        if existing_lead:
            # Update existing lead with new info
            updated = False
            if detected["email"] and not existing_lead.email:
                existing_lead.email = detected["email"]
                updated = True
            if detected["phone"] and not existing_lead.phone:
                existing_lead.phone = detected["phone"]
                updated = True
            if detected["name"] and not existing_lead.name:
                existing_lead.name = detected["name"]
                updated = True
            
            if updated:
                existing_lead.detected_fields = detected
                existing_lead.detection_confidence = max(
                    existing_lead.detection_confidence,
                    detected["confidence"]
                )
                existing_lead.updated_at = datetime.utcnow()
                self.db.commit()
            
            return existing_lead
        
        # Create new lead
        lead = Lead(
            tenant_id=tenant_id,
            bot_id=conversation.bot_id,
            conversation_id=conversation.id,
            name=detected["name"],
            email=detected["email"],
            phone=detected["phone"],
            source=LeadSource.WHATSAPP.value if conversation.source == "whatsapp" else LeadSource.WEB_WIDGET.value,
            status=LeadStatus.NEW.value,
            is_auto_detected=True,
            detection_confidence=detected["confidence"],
            detected_fields=detected
        )
        
        self.db.add(lead)
        
        # Update conversation
        conversation.has_lead = True
        conversation.lead_score = int(detected["confidence"] * 100)
        
        self.db.commit()
        self.db.refresh(lead)
        
        return lead
    
    def calculate_lead_score(self, lead: Lead) -> int:
        """
        Calculate lead score based on available information.
        
        Score ranges from 0-100.
        """
        score = 0
        
        # Contact info completeness
        if lead.email:
            score += 30
        if lead.phone:
            score += 30
        if lead.name:
            score += 20
        if lead.company:
            score += 10
        
        # Detection confidence
        score += int(lead.detection_confidence * 10)
        
        return min(score, 100)
    
    def enrich_lead(
        self,
        lead_id: uuid.UUID,
        data: dict
    ) -> Optional[Lead]:
        """
        Enrich lead with additional data.
        """
        lead = self.db.query(Lead).filter(
            Lead.id == lead_id,
            Lead.is_deleted == False
        ).first()
        
        if not lead:
            return None
        
        # Update fields
        if "name" in data:
            lead.name = data["name"]
        if "email" in data:
            lead.email = data["email"]
        if "phone" in data:
            lead.phone = data["phone"]
        if "company" in data:
            lead.company = data["company"]
        if "notes" in data:
            lead.notes = data["notes"]
        if "tags" in data:
            lead.tags = data["tags"]
        if "status" in data:
            lead.status = data["status"]
        
        # Recalculate score
        lead.score = self.calculate_lead_score(lead)
        lead.updated_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(lead)
        
        return lead


# Singleton instance
lead_detection_service = None

def get_lead_detection_service(db: Session) -> LeadDetectionService:
    """Get or create lead detection service instance."""
    return LeadDetectionService(db)

