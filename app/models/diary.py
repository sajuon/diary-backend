from sqlalchemy import (
    BigInteger,
    Date,
    ForeignKey,
    UniqueConstraint,
    Text,
    JSON,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class DiaryEntry(TimestampMixin, Base):
    __tablename__ = "diary_entries"
    __table_args__ = (
        UniqueConstraint("user_id", "entry_date", name="uq_user_entry_date"),
        {"mysql_engine": "InnoDB"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    entry_date: Mapped[object] = mapped_column(Date, nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    weather: Mapped[str | None] = mapped_column(String(20), nullable=True)
    mood_tags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    summary_tag: Mapped[str | None] = mapped_column(String(20), nullable=True)

    user = relationship("User", back_populates="diary_entries")

    letter = relationship(
        "OtterLetter",
        back_populates="diary_entry",
        uselist=False,
        cascade="all, delete-orphan",
    )