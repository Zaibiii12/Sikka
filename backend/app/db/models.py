from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class IndexerState(Base):
    """
    Stores the last safely indexed block.

    This makes the indexer restart-safe: after a crash or laptop reboot,
    it continues from the last committed checkpoint instead of starting
    from genesis or silently skipping blocks.
    """

    __tablename__ = "indexer_state"

    key: Mapped[str] = mapped_column(
        String(100),
        primary_key=True,
    )

    last_block: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
    )

    last_block_hash: Mapped[str | None] = mapped_column(
        String(66),
        nullable=True,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class ChainEvent(Base):
    """
    Immutable-ish decoded event audit log.

    The unique chain_id + tx_hash + log_index constraint makes repeated
    indexing idempotent: the same blockchain log cannot be inserted twice.
    """

    __tablename__ = "chain_events"

    __table_args__ = (
        UniqueConstraint(
            "chain_id",
            "transaction_hash",
            "log_index",
            name="uq_chain_event_log",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    chain_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    contract_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    contract_address: Mapped[str] = mapped_column(
        String(42),
        nullable=False,
        index=True,
    )

    event_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    block_number: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        index=True,
    )

    block_hash: Mapped[str] = mapped_column(
        String(66),
        nullable=False,
    )

    transaction_hash: Mapped[str] = mapped_column(
        String(66),
        nullable=False,
        index=True,
    )

    transaction_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    log_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    block_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    decoded_args: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    indexed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class PaymentRecord(Base):
    """
    Derived searchable representation of PaymentSubmitted events.

    The blockchain remains the source of truth. This table exists to make
    API history queries fast and practical.
    """

    __tablename__ = "payments"

    payment_id: Mapped[str] = mapped_column(
        String(66),
        primary_key=True,
    )

    from_address: Mapped[str] = mapped_column(
        String(42),
        nullable=False,
        index=True,
    )

    to_address: Mapped[str] = mapped_column(
        String(42),
        nullable=False,
        index=True,
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(78, 0),
        nullable=False,
    )

    nonce: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    transaction_hash: Mapped[str] = mapped_column(
        String(66),
        nullable=False,
        unique=True,
        index=True,
    )

    block_number: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        index=True,
    )

    block_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )


class SettlementRecord(Base):
    __tablename__ = "settlements"

    batch_id: Mapped[str] = mapped_column(
        String(66),
        primary_key=True,
    )

    payment_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    settled_by: Mapped[str] = mapped_column(
        String(42),
        nullable=False,
        index=True,
    )

    transaction_hash: Mapped[str] = mapped_column(
        String(66),
        nullable=False,
        unique=True,
        index=True,
    )

    block_number: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        index=True,
    )

    settled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )


class SettlementPayment(Base):
    """
    Links individual processed payments to exactly one settlement batch.
    """

    __tablename__ = "settlement_payments"

    batch_id: Mapped[str] = mapped_column(
        String(66),
        ForeignKey(
            "settlements.batch_id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )

    payment_id: Mapped[str] = mapped_column(
        String(66),
        ForeignKey(
            "payments.payment_id",
            ondelete="CASCADE",
        ),
        primary_key=True,
        unique=True,
    )


class BankRecord(Base):
    """
    Current indexed bank state reconstructed from registry events.
    """

    __tablename__ = "banks"

    address: Mapped[str] = mapped_column(
        String(42),
        primary_key=True,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    last_updated_block: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )


class TokenTransfer(Base):
    """
    Indexed ERC-20 Transfer events.

    Mint and burn are also represented by ERC-20 Transfer events where
    either the source or destination is the zero address.
    """

    __tablename__ = "token_transfers"

    __table_args__ = (
        UniqueConstraint(
            "transaction_hash",
            "log_index",
            name="uq_token_transfer_log",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    from_address: Mapped[str] = mapped_column(
        String(42),
        nullable=False,
        index=True,
    )

    to_address: Mapped[str] = mapped_column(
        String(42),
        nullable=False,
        index=True,
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(78, 0),
        nullable=False,
    )

    transaction_hash: Mapped[str] = mapped_column(
        String(66),
        nullable=False,
        index=True,
    )

    block_number: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        index=True,
    )

    log_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    block_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
