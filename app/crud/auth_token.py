from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime

from app.models.auth_token import AuthToken


def is_blacklisted(db: Session, token_jti: str) -> bool:
    q = db.query(AuthToken).filter(AuthToken.token_jti == token_jti)
    return db.query(q.exists()).scalar()


def add_to_blacklist(
    db: Session,
    user_id: int,
    token_jti: str,
    token_type: str,
    expires_at: datetime,
    reason: Optional[str] = None,
) -> AuthToken:
    exists = db.query(AuthToken).filter(AuthToken.token_jti == token_jti).first()
    if exists:
        return exists

    row = AuthToken(
        user_id=user_id,
        token_jti=token_jti,
        token_type=token_type,
        expires_at=expires_at,
        revoked_at=datetime.utcnow(),
        reason=reason,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def cleanup_expired(db: Session) -> int:
    """
    만료된 블랙리스트 토큰 정리(선택)
    return: 삭제된 row 수
    """
    now = datetime.utcnow()
    deleted = (
        db.query(AuthToken)
        .filter(AuthToken.expires_at < now)
        .delete(synchronize_session=False)
    )
    db.commit()
    return deleted
