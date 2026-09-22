from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class BankAccountRecord(Base):
    __tablename__ = "bank_accounts"

    __table_args__ = (
        CheckConstraint(
            "currency <> ''",
            name=(
                "ck_bank_accounts_"
                "currency_nonempty"
            ),
        ),
    )

    account_id: Mapped[str] = (
        mapped_column(
            String(100),
            primary_key=True,
        )
    )

    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
    )

    active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    created_at: Mapped[datetime] = (
        mapped_column(
            DateTime(timezone=True),
            nullable=False,
            default=_utcnow,
        )
    )

    updated_at: Mapped[datetime] = (
        mapped_column(
            DateTime(timezone=True),
            nullable=False,
            default=_utcnow,
        )
    )


class BankTransactionRecord(Base):
    __tablename__ = "bank_transactions"

    __table_args__ = (
        CheckConstraint(
            (
                "direction IN "
                "('CREDIT', 'DEBIT')"
            ),
            name=(
                "ck_bank_transactions_"
                "direction"
            ),
        ),
        CheckConstraint(
            (
                "status IN "
                "("
                "'INITIATED', "
                "'PENDING', "
                "'SETTLED', "
                "'FAILED', "
                "'REVERSED'"
                ")"
            ),
            name=(
                "ck_bank_transactions_"
                "status"
            ),
        ),
        CheckConstraint(
            "amount_micro > 0",
            name=(
                "ck_bank_transactions_"
                "amount_positive"
            ),
        ),
        CheckConstraint(
            "currency <> ''",
            name=(
                "ck_bank_transactions_"
                "currency_nonempty"
            ),
        ),
        Index(
            "ix_bank_transactions_"
            "account_created",
            "account_id",
            "created_at",
        ),
        Index(
            "ix_bank_transactions_status",
            "status",
        ),
    )

    transaction_id: Mapped[str] = (
        mapped_column(
            String(150),
            primary_key=True,
        )
    )

    account_id: Mapped[str] = (
        mapped_column(
            String(100),
            ForeignKey(
                "bank_accounts.account_id",
                ondelete="RESTRICT",
            ),
            nullable=False,
        )
    )

    direction: Mapped[str] = (
        mapped_column(
            String(10),
            nullable=False,
        )
    )

    currency: Mapped[str] = (
        mapped_column(
            String(3),
            nullable=False,
        )
    )

    amount_micro: Mapped[Decimal] = (
        mapped_column(
            Numeric(78, 0),
            nullable=False,
        )
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    created_at: Mapped[datetime] = (
        mapped_column(
            DateTime(timezone=True),
            nullable=False,
            default=_utcnow,
        )
    )

    updated_at: Mapped[datetime] = (
        mapped_column(
            DateTime(timezone=True),
            nullable=False,
            default=_utcnow,
        )
    )

    settled_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
