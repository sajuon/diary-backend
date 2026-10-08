from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin

DEFAULT_THEME_KEY = "default"


class UserRoom(TimestampMixin, Base):
    """사용자 꾸미기 설정. 사용자당 1행. 방 테마·편지지, 이후 소품 배치도 여기에 붙인다."""

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
    letter_paper_key: Mapped[str] = mapped_column(
        String(50), nullable=False, default=DEFAULT_THEME_KEY
    )
