from sqlalchemy import BigInteger, Date, Time, String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class UserBirthProfile(TimestampMixin, Base):
    __tablename__ = "user_birth_profiles"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_birth_profile_user_id"),
        {"mysql_engine": "InnoDB"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    birth_date: Mapped[object | None] = mapped_column(Date, nullable=True)
    birth_time: Mapped[object | None] = mapped_column(Time, nullable=True)
    birth_place: Mapped[str | None] = mapped_column(String(100), nullable=True)
    sex: Mapped[str | None] = mapped_column(String(10), nullable=True)
    timezone: Mapped[str] = mapped_column(String(50), nullable=False, default="Asia/Seoul")

    user = relationship("User", back_populates="birth_profile")
