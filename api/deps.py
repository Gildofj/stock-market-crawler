import uuid
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from crawler.models.models import User
from crawler.services.database import get_db as get_crawler_db

DBDep = Annotated[Session, Depends(get_crawler_db)]


def require_premium_user(
    db: DBDep,
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> User:
    """Validates that the caller is a premium user.

    Expects an `X-User-Id` header carrying the user UUID. The API key check
    runs upstream via the global router dependency; this dependency only
    answers the premium gating question.
    """
    if not x_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-User-Id header.",
        )
    try:
        user_uuid = uuid.UUID(x_user_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-User-Id must be a valid UUID.",
        ) from exc

    user = db.query(User).filter(User.id == user_uuid).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found.",
        )
    if not user.is_premium:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Premium plan required.",
        )
    return user


PremiumUserDep = Annotated[User, Depends(require_premium_user)]
