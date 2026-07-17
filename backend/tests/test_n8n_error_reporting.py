from __future__ import annotations

import uuid

from app.models.automation import AutomationRun
from app.models.incident import Incident
from app.models.system_event import SystemEvent
from app.models.tenant import Tenant
from app.models.user import User


def test_n8n_error_report_creates_deduplicated_incident(client, monkeypatch):
    from app.core.config import settings
    from app.db import session as session_module

    monkeypatch.setattr(settings, "N8N_ERROR_WEBHOOK_SECRET", "test-error-secret")
    db = session_module.SessionLocal()
    try:
        user = User(
            email=f"n8n-error-{uuid.uuid4().hex}@example.com",
            password_hash="unused",
            full_name="n8n Error Test",
        )
        db.add(user)
        db.flush()
        tenant = Tenant(
            name="n8n Error Tenant",
            slug=f"n8n-error-{uuid.uuid4().hex}",
            owner_id=user.id,
        )
        db.add(tenant)
        db.flush()
        run = AutomationRun(
            tenant_id=str(tenant.id),
            channel="whatsapp",
            from_number="905551112233",
            message_id=f"error-{uuid.uuid4()}",
            n8n_workflow_id="workflow-1",
            n8n_execution_id="execution-500",
            status="failed",
            correlation_id="correlation-500",
        )
        db.add(run)
        db.commit()

        payload = {
            "executionId": "execution-500",
            "workflowId": "workflow-1",
            "workflowName": "SvontAI Test Workflow",
            "lastNode": "Failing Node",
            "errorMessage": "Provider timeout",
            "mode": "webhook",
        }
        headers = {"Authorization": "Bearer test-error-secret"}
        first = client.post("/api/v1/n8n/errors/report", json=payload, headers=headers)
        second = client.post("/api/v1/n8n/errors/report", json=payload, headers=headers)
        assert first.status_code == 200, first.text
        assert second.status_code == 200, second.text
        assert first.json()["tenant_id"] == str(tenant.id)
        assert first.json()["incident_id"] == second.json()["incident_id"]

        incidents = db.query(Incident).filter(
            Incident.tenant_id == str(tenant.id),
            Incident.title == "n8n workflow failed: SvontAI Test Workflow",
        ).all()
        events = db.query(SystemEvent).filter(
            SystemEvent.tenant_id == str(tenant.id),
            SystemEvent.code == "N8N_EXECUTION_FAILED",
        ).all()
        assert len(incidents) == 1
        assert len(events) == 2
    finally:
        db.close()


def test_n8n_error_report_rejects_invalid_bearer(client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "N8N_ERROR_WEBHOOK_SECRET", "test-error-secret")
    response = client.post(
        "/api/v1/n8n/errors/report",
        headers={"Authorization": "Bearer wrong"},
        json={
            "executionId": "execution-1",
            "workflowName": "Test",
            "errorMessage": "Failure",
        },
    )
    assert response.status_code == 401
