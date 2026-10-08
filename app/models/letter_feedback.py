from sqlalchemy import BigInteger, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class LetterFeedback(TimestampMixin, Base):
    """해도리 편지에 대한 사용자 피드백 (좋아요/아쉬워요 + 한마디). 편지 1통당 1개."""

    __tablename__ = "letter_feedback"
    __table_args__ = (
        UniqueConstraint("letter_id", name="uq_letter_feedback_letter_id"),
        {"mysql_engine": "InnoDB"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    letter_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("otter_letters.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    rating: Mapped[str] = mapped_column(String(10), nullable=False)  # "like" | "dislike"
    comment: Mapped[str] = mapped_column(String(300), nullable=False, default="")
