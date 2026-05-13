# /home/dori/diary-backend/app/models/diary.py

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
        UniqueConstraint(
            "user_id",
            "entry_date",
            "diary_type",
            name="uq_user_entry_date_diary_type",
        ),
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

    # question: 질문형 일기
    # free: 자유 일기
    # 하루에 question 1개 + free 1개까지 저장 가능
    diary_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="free",
        server_default="free",
        index=True,
    )

    # 질문형 일기 고정 ID
    # 예: 03-01, 05-12
    # 자유형 일기일 때는 NULL
    question_id: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        index=True,
    )

    # 질문형 일기일 때 오늘의 질문 문구 저장
    # 자유형 일기일 때는 NULL
    question_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    user = relationship("User", back_populates="diary_entries")

    letter = relationship(
        "OtterLetter",
        back_populates="diary_entry",
        uselist=False,
        cascade="all, delete-orphan",
    )