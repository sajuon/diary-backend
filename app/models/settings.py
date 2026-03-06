from datetime import time

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

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # 전체 알림 on/off
    push_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # 개별 알림 on/off
    fortune_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    diary_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    reply_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # 알림 시간
    fortune_time: Mapped[time] = mapped_column(Time, nullable=False, default=time(8, 0, 0))
    diary_time: Mapped[time] = mapped_column(Time, nullable=False, default=time(21, 0, 0))
    reply_time: Mapped[time] = mapped_column(Time, nullable=False, default=time(8, 0, 0))

    # 추후 모바일 푸시/테스트용
    device_tokens: Mapped[list | None] = mapped_column(JSON, nullable=True, default=list)

    user = relationship("User", back_populates="notification_settings")