"""
Workspace notes routes.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_tenant, get_current_user
from app.dependencies.permissions import require_permissions
from app.models.note import WorkspaceNote
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.note import NoteCreate, NoteResponse, NoteUpdate
from app.services.audit_log_service import AuditLogService

router = APIRouter(prefix="/notes", tags=["Notes"])


@router.get("", response_model=list[NoteResponse])
async def list_notes(
    archived: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tools:read"]))
):
    notes = db.query(WorkspaceNote).filter(
        WorkspaceNote.tenant_id == current_tenant.id,
        WorkspaceNote.archived == archived
    ).order_by(WorkspaceNote.pinned.desc(), WorkspaceNote.updated_at.desc()).all()
    return [NoteResponse.model_validate(item) for item in notes]


@router.post("", response_model=NoteResponse, status_code=status.HTTP_201_CREATED)
async def create_note(
    payload: NoteCreate,
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["dashboard:edit"]))
):
    note = WorkspaceNote(
        tenant_id=current_tenant.id,
        created_by=current_user.id,
        title=payload.title,
        content=payload.content,
        color=payload.color,
        pinned=payload.pinned,
        position_x=payload.position_x,
        position_y=payload.position_y,
        archived=False
    )
    db.add(note)
    db.commit()
    db.refresh(note)

    AuditLogService(db).log(
        action="note.create",
        tenant_id=str(current_tenant.id),
        user_id=str(current_user.id),
        resource_type="note",
        resource_id=str(note.id),
        payload={"title": note.title, "color": note.color}
    )

    return NoteResponse.model_validate(note)


@router.patch("/{note_id}", response_model=NoteResponse)
async def update_note(
    note_id: UUID,
    payload: NoteUpdate,
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["dashboard:edit"]))
):
    note = db.query(WorkspaceNote).filter(
        WorkspaceNote.id == note_id,
        WorkspaceNote.tenant_id == current_tenant.id
    ).first()
    if not note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not bulunamadı")

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(note, key, value)
    db.commit()
    db.refresh(note)

    AuditLogService(db).log(
        action="note.update",
        tenant_id=str(current_tenant.id),
        user_id=str(current_user.id),
        resource_type="note",
        resource_id=str(note.id),
        payload=update_data
    )

    return NoteResponse.model_validate(note)


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(
    note_id: UUID,
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["dashboard:edit"]))
):
    note = db.query(WorkspaceNote).filter(
        WorkspaceNote.id == note_id,
        WorkspaceNote.tenant_id == current_tenant.id
    ).first()
    if not note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not bulunamadı")

    db.delete(note)
    db.commit()

    AuditLogService(db).log(
        action="note.delete",
        tenant_id=str(current_tenant.id),
        user_id=str(current_user.id),
        resource_type="note",
        resource_id=str(note_id),
        payload={}
    )
