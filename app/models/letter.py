from sqlalchemy import (
    BigInteger,
    Date,
    ForeignKey,
    UniqueConstraint,
    Text,
    String,
    JSON,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class OtterLetter(TimestampMixin, Base):
    __tablename__ = "otter_letters"
    __table_args__ = (
        UniqueConstraint("diary_entry_id", name="uq_letter_diary_entry_id"),
        {"mysql_engine": "InnoDB"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    diary_entry_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("diary_entries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    letter_date: Mapped[object] = mapped_column(Date, nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")

    element_hint: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    model: Mapped[str | None] = mapped_column(String(50), nullable=True)

    user = relationship("User", back_populates="letters")
    diary_entry = relationship("DiaryEntry", back_populates="letter")
