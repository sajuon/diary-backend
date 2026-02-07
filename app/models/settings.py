from sqlalchemy import BigInteger, Boolean, Time, ForeignKey, UniqueConstraint, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class NotificationSettings(TimestampMixin, Base):
    __tablename__ = "notification_settings"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_notification_settings_user_id"),
        {"mysql_engine": "InnoDB"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    fortune_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    diary_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    fortune_time: Mapped[object] = mapped_column(Time, nullable=False)
    diary_time: Mapped[object] = mapped_column(Time, nullable=False)

    device_tokens: Mapped[list | None] = mapped_column(JSON, nullable=True)

    user = relationship("User", back_populates="notification_settings")
