from sqlalchemy import JSON, BigInteger, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class HaedoriState(TimestampMixin, Base):
    """
    사용자별 해도리 상태. 사용자당 1행.

    - 성격 점수 4개: 간식을 먹을 때마다 쌓인다 (줄어들지 않음)
    - snacks: 가지고 있는 간식 개수 {"strawberry_cake": 2, ...}
    """

    __tablename__ = "haedori_states"
    __table_args__ = {"mysql_engine": "InnoDB"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    cheer: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    listen: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    playful: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    advice: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    snacks: Mapped[dict | None] = mapped_column(JSON, nullable=True)
