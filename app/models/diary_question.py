from datetime import datetime

from sqlalchemy import BigInteger, Column, Date, DateTime, ForeignKey, String, UniqueConstraint, Index
from sqlalchemy.orm import relationship

from app.models.base import Base


class DiaryQuestion(Base):
    __tablename__ = "diary_questions"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    entry_date = Column(Date, nullable=False)
    question_text = Column(String(255), nullable=False)
    question_hash = Column(String(64), nullable=False)
    model_name = Column(String(100), nullable=True)
    source_type = Column(String(20), nullable=False, default="llm")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    user = relationship("User", backref="diary_questions")

    __table_args__ = (
        UniqueConstraint("user_id", "entry_date", name="uq_diary_questions_user_date"),
        UniqueConstraint("user_id", "question_hash", name="uq_diary_questions_user_hash"),
        Index("idx_diary_questions_user_created", "user_id", "created_at"),
        Index("idx_diary_questions_entry_date", "entry_date"),
    )