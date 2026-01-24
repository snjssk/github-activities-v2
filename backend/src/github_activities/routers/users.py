"""Users API router."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func

from ..models import User, Activity, get_session

router = APIRouter(prefix="/api/users", tags=["users"])


class UserResponse(BaseModel):
    """User response model."""
    id: int
    username: str
    display_name: Optional[str]
    last_collected_at: Optional[datetime]
    collect_from_date: Optional[str]
    activity_count: int

    class Config:
        from_attributes = True


@router.get("", response_model=list[UserResponse])
def list_users():
    """List all users with their collection status."""
    with get_session() as session:
        users = session.execute(select(User).order_by(User.username)).scalars().all()

        result = []
        for user in users:
            count = session.execute(
                select(func.count(Activity.id)).where(Activity.user_id == user.id)
            ).scalar() or 0

            result.append(UserResponse(
                id=user.id,
                username=user.username,
                display_name=user.display_name,
                last_collected_at=user.last_collected_at,
                collect_from_date=user.collect_from_date.isoformat() if user.collect_from_date else None,
                activity_count=count,
            ))

        return result


@router.get("/{username}", response_model=UserResponse)
def get_user(username: str):
    """Get a specific user."""
    with get_session() as session:
        user = session.execute(
            select(User).where(User.username == username)
        ).scalar_one_or_none()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        count = session.execute(
            select(func.count(Activity.id)).where(Activity.user_id == user.id)
        ).scalar() or 0

        return UserResponse(
            id=user.id,
            username=user.username,
            display_name=user.display_name,
            last_collected_at=user.last_collected_at,
            collect_from_date=user.collect_from_date.isoformat() if user.collect_from_date else None,
            activity_count=count,
        )
