from sqlalchemy import BigInteger, String, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class AuthToken(Base):
    """
    JWT 블랙리스트(로그아웃/강제만료) 저장용
    - 권장: token_jti(JWT의 jti 클레임)로 저장
    """
    __tablename__ = "auth_tokens"
    __table_args__ = (
        UniqueConstraint("token_jti", name="uq_auth_tokens_token_jti"),
        Index("ix_auth_tokens_user_id", "user_id"),
        {"mysql_engine": "InnoDB"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    token_jti: Mapped[str] = mapped_column(String(255), nullable=False)
    token_type: Mapped[str] = mapped_column(String(20), nullable=False, default="access")

    expires_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(100), nullable=True)

    user = relationship("User", back_populates="auth_tokens")
