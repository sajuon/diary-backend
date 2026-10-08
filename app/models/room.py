from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin

DEFAULT_THEME_KEY = "default"


class UserRoom(TimestampMixin, Base):
    """해도리 방 설정. 사용자당 1행. 지금은 적용 중인 테마만, 이후 소품 배치도 여기에 붙인다."""

    __tablename__ = "user_rooms"
    __table_args__ = {"mysql_engine": "InnoDB"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    theme_key: Mapped[str] = mapped_column(String(50), nullable=False, default=DEFAULT_THEME_KEY)
