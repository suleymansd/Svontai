"""
User management router.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.user import UserResponse, UserUpdate, UserWithTenants

router = APIRouter(prefix="/me", tags=["Users"])


@router.get("", response_model=UserWithTenants)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> User:
    """
    Get current user information with tenants.
    
    Args:
        current_user: The authenticated user.
        db: Database session.
    
    Returns:
        User information with associated tenants.
    """
    # Eager load tenants
    db.refresh(current_user, ["tenants"])
    return current_user


@router.put("", response_model=UserResponse)
async def update_current_user(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> User:
    """
    Update current user information.
    
    Args:
        user_update: Fields to update.
        current_user: The authenticated user.
        db: Database session.
    
    Returns:
        Updated user information.
    """
    update_data = user_update.model_dump(exclude_unset=True)
    
    for field, value in update_data.items():
        setattr(current_user, field, value)
    
    db.commit()
    db.refresh(current_user)
    
    return current_user

