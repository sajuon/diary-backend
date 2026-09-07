from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.models.base import Base


class MonthlyReport(Base):
    __tablename__ = "monthly_reports"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)

    summary = Column(Text, nullable=False)
    highlights = Column(Text, nullable=False)
    comment = Column(Text, nullable=False)
    insights = Column(Text, nullable=True)

    entry_count = Column(Integer, nullable=False, default=0)
    source_type = Column(String(20), nullable=False, default="llm")
    model_name = Column(String(100), nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    user = relationship("User", backref="monthly_reports")

    __table_args__ = (
        UniqueConstraint("user_id", "year", "month", name="uq_monthly_reports_user_ym"),
        Index("idx_monthly_reports_user_ym", "user_id", "year", "month"),
    )