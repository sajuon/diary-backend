from sqlalchemy import BigInteger, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class PearlTransaction(TimestampMixin, Base):
    """
    진주 지급/사용 내역.

    (user_id, reason, ref_key) 유니크 제약으로 같은 보상이 두 번 지급되는 것을 막는다.
    - 하루 1번 보상: ref_key = KST 날짜 (예: "2026-10-08")
    - 편지 피드백: ref_key = "letter:<letter_id>"
    - 포춘쿠키처럼 반복 가능한 내역: ref_key = NULL (유니크 검사 대상 아님)
    """

    __tablename__ = "pearl_transactions"
    __table_args__ = (
        UniqueConstraint("user_id", "reason", "ref_key", name="uq_pearl_tx_user_reason_ref"),
        {"mysql_engine": "InnoDB"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(40), nullable=False)
    ref_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)
