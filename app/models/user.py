from sqlalchemy import BigInteger, String, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = {"mysql_engine": "InnoDB"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    email: Mapped[str | None] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=True,
    )
    password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    nickname: Mapped[str] = mapped_column(String(50), nullable=False)
    profile_image: Mapped[str | None] = mapped_column(String(255), nullable=True)

    provider: Mapped[str] = mapped_column(String(20), nullable=False, default="local")
    provider_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )

    pearls: Mapped[int] = mapped_column(Integer, nullable=False, default=100)

    birth_profile = relationship(
        "UserBirthProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )

    notification_settings = relationship(
        "NotificationSettings",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )

    web_push_subscriptions = relationship(
        "WebPushSubscription",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    fortunes = relationship(
        "DailyFortune",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    diary_entries = relationship(
        "DiaryEntry",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    letters = relationship(
        "OtterLetter",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    auth_tokens = relationship(
        "AuthToken",
        back_populates="user",
        cascade="all, delete-orphan",
    )