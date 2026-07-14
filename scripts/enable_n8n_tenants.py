#!/usr/bin/env python3
"""Enable the configured n8n workflow for existing SmartWA tenants."""

from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import settings  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.automation import TenantAutomationSettings  # noqa: E402
from app.models.tenant import Tenant  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    workflow_id = settings.N8N_INCOMING_WORKFLOW_ID.strip()
    if not settings.USE_N8N or not workflow_id:
        print("USE_N8N=true and N8N_INCOMING_WORKFLOW_ID are required.")
        return 1

    db = SessionLocal()
    try:
        tenants = db.query(Tenant).all()
        created = 0
        updated = 0
        for tenant in tenants:
            row = db.query(TenantAutomationSettings).filter(
                TenantAutomationSettings.tenant_id == str(tenant.id)
            ).first()
            if row is None:
                created += 1
                if args.apply:
                    db.add(TenantAutomationSettings(
                        id=str(uuid.uuid4()),
                        tenant_id=str(tenant.id),
                        use_n8n=True,
                        default_workflow_id=workflow_id,
                        whatsapp_workflow_id=workflow_id,
                    ))
                continue

            needs_update = (
                not row.use_n8n
                or row.default_workflow_id != workflow_id
                or row.whatsapp_workflow_id != workflow_id
            )
            if needs_update:
                updated += 1
                if args.apply:
                    row.use_n8n = True
                    row.default_workflow_id = workflow_id
                    row.whatsapp_workflow_id = workflow_id

        if args.apply:
            db.commit()
        print({
            "mode": "apply" if args.apply else "dry-run",
            "tenants": len(tenants),
            "create": created,
            "update": updated,
            "workflow_id": workflow_id,
        })
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
