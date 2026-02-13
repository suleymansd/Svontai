"""Service for creating and updating incidents."""

from sqlalchemy.orm import Session

from app.models.incident import Incident


class IncidentService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, data: dict) -> Incident:
        incident = Incident(**data)
        self.db.add(incident)
        self.db.commit()
        self.db.refresh(incident)
        return incident

    def update(self, incident: Incident, data: dict) -> Incident:
        for key, value in data.items():
            setattr(incident, key, value)
        self.db.commit()
        self.db.refresh(incident)
        return incident
