from sqlalchemy.orm import Session
from typing import Optional

from app.models.user import User


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    # email may be null/None for social-only accounts
    return db.query(User).filter(User.email == email).first()


def get_user_by_provider(db: Session, provider: str, provider_id: str) -> Optional[User]:
    return (
        db.query(User)
        .filter(User.provider == provider, User.provider_id == provider_id)
        .first()
    )


def create_user(
    db: Session,
    nickname: str,
    email: Optional[str] = None,
    hashed_password: Optional[str] = None,
    provider: str = "local",
    provider_id: Optional[str] = None,
) -> User:
    user = User(
        email=email,
        password=hashed_password,
        nickname=nickname,
        provider=provider,
        provider_id=provider_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_user_profile(
    db: Session,
    user: User,
    nickname: Optional[str] = None,
    profile_image: Optional[str] = None,
) -> User:
    if nickname is not None:
        user.nickname = nickname
    if profile_image is not None:
        user.profile_image = profile_image

    db.commit()
    db.refresh(user)
    return user
