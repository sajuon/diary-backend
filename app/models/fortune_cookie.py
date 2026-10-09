from sqlalchemy import BigInteger, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class FortuneCookie(TimestampMixin, Base):
    """
    하루에 연 포춘쿠키 기록.

    - kind: "free"(오늘의 포춘쿠키, 무료) / "paid"(상점 구매)
    - date_key: KST 날짜 (예: "2026-10-09")
    (user_id, kind, date_key) 유니크 제약으로 종류별 하루 1개만 열 수 있다.
    """

    __tablename__ = "fortune_cookies"
    __table_args__ = (
        UniqueConstraint("user_id", "kind", "date_key", name="uq_fortune_cookie_user_kind_date"),
        {"mysql_engine": "InnoDB"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    date_key: Mapped[str] = mapped_column(String(10), nullable=False)
    reward: Mapped[int] = mapped_column(Integer, nullable=False)
    message: Mapped[str] = mapped_column(String(200), nullable=False)
    source: Mapped[str] = mapped_column(String(10), nullable=False, default="llm")
