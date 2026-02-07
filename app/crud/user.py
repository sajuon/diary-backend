from sqlalchemy.orm import Session
from typing import Optional

from app.models.user import User


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email).first()


def create_user(db: Session, email: str, hashed_password: str, nickname: str) -> User:
    user = User(email=email, password=hashed_password, nickname=nickname)
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
