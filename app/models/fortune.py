from sqlalchemy import (
    BigInteger,
    Date,
    String,
    Text,
    ForeignKey,
    UniqueConstraint,
    JSON,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class DailyFortune(TimestampMixin, Base):
    __tablename__ = "daily_fortunes"
    __table_args__ = (
        UniqueConstraint("user_id", "fortune_date", name="uq_user_fortune_date"),
        {"mysql_engine": "InnoDB"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    fortune_date: Mapped[object] = mapped_column(Date, nullable=False, index=True)

    love: Mapped[str] = mapped_column(Text, nullable=False, default="")
    study: Mapped[str] = mapped_column(Text, nullable=False, default="")
    caution: Mapped[str] = mapped_column(Text, nullable=False, default="")
    good_thing: Mapped[str] = mapped_column(Text, nullable=False, default="")
    ritual: Mapped[str] = mapped_column(Text, nullable=False, default="")

    element_hint: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    model: Mapped[str | None] = mapped_column(String(50), nullable=True)

    user = relationship("User", back_populates="fortunes")