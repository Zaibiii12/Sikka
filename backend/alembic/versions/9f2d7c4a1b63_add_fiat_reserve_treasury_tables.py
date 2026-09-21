"""add fiat reserve treasury tables

Revision ID: 9f2d7c4a1b63
Revises: e528a73157d3
Create Date: 2026-09-20
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "9f2d7c4a1b63"
down_revision: Union[str, Sequence[str], None] = "e528a73157d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "reserve_accounts",
        sa.Column(
            "currency",
            sa.String(length=3),
            nullable=False,
        ),
        sa.Column(
            "verified_balance",
            sa.Numeric(precision=78, scale=0),
            nullable=False,
        ),
        sa.Column(
            "reserved_balance",
            sa.Numeric(precision=78, scale=0),
            nullable=False,
        ),
        sa.Column(
            "source_type",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column(
            "version",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "verified_balance >= 0",
            name="ck_reserve_verified_nonnegative",
        ),
        sa.CheckConstraint(
            "reserved_balance >= 0",
            name="ck_reserve_reserved_nonnegative",
        ),
        sa.CheckConstraint(
            "reserved_balance <= verified_balance",
            name="ck_reserve_reserved_within_verified",
        ),
        sa.PrimaryKeyConstraint(
            "currency",
        ),
    )

    op.create_table(
        "fiat_movements",
        sa.Column(
            "id",
            sa.BigInteger(),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "reference",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column(
            "movement_type",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column(
            "currency",
            sa.String(length=3),
            nullable=False,
        ),
        sa.Column(
            "amount",
            sa.Numeric(precision=78, scale=0),
            nullable=False,
        ),
        sa.Column(
            "bank_address",
            sa.String(length=42),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column(
            "external_reference",
            sa.String(length=255),
            nullable=True,
        ),
        sa.Column(
            "details",
            postgresql.JSONB(
                astext_type=sa.Text(),
            ),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "verified_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.CheckConstraint(
            "amount > 0",
            name="ck_fiat_movement_amount_positive",
        ),
        sa.ForeignKeyConstraint(
            ["currency"],
            ["reserve_accounts.currency"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "id",
        ),
        sa.UniqueConstraint(
            "reference",
            name="uq_fiat_movement_reference",
        ),
    )

    op.create_index(
        op.f(
            "ix_fiat_movements_movement_type"
        ),
        "fiat_movements",
        ["movement_type"],
        unique=False,
    )

    op.create_index(
        op.f(
            "ix_fiat_movements_currency"
        ),
        "fiat_movements",
        ["currency"],
        unique=False,
    )

    op.create_index(
        op.f(
            "ix_fiat_movements_bank_address"
        ),
        "fiat_movements",
        ["bank_address"],
        unique=False,
    )

    op.create_index(
        op.f(
            "ix_fiat_movements_status"
        ),
        "fiat_movements",
        ["status"],
        unique=False,
    )

    op.create_table(
        "mint_requests",
        sa.Column(
            "request_id",
            sa.String(length=66),
            nullable=False,
        ),
        sa.Column(
            "bank_address",
            sa.String(length=42),
            nullable=False,
        ),
        sa.Column(
            "currency",
            sa.String(length=3),
            nullable=False,
        ),
        sa.Column(
            "amount",
            sa.Numeric(precision=78, scale=0),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column(
            "reserve_movement_id",
            sa.BigInteger(),
            nullable=True,
        ),
        sa.Column(
            "transaction_hash",
            sa.String(length=66),
            nullable=True,
        ),
        sa.Column(
            "block_number",
            sa.BigInteger(),
            nullable=True,
        ),
        sa.Column(
            "failure_reason",
            sa.String(length=500),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "amount > 0",
            name="ck_mint_request_amount_positive",
        ),
        sa.ForeignKeyConstraint(
            ["currency"],
            ["reserve_accounts.currency"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["reserve_movement_id"],
            ["fiat_movements.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint(
            "request_id",
        ),
    )

    op.create_index(
        op.f(
            "ix_mint_requests_bank_address"
        ),
        "mint_requests",
        ["bank_address"],
        unique=False,
    )

    op.create_index(
        op.f(
            "ix_mint_requests_status"
        ),
        "mint_requests",
        ["status"],
        unique=False,
    )

    op.create_index(
        op.f(
            "ix_mint_requests_transaction_hash"
        ),
        "mint_requests",
        ["transaction_hash"],
        unique=False,
    )

    op.create_table(
        "redemption_requests",
        sa.Column(
            "request_id",
            sa.String(length=66),
            nullable=False,
        ),
        sa.Column(
            "bank_address",
            sa.String(length=42),
            nullable=False,
        ),
        sa.Column(
            "currency",
            sa.String(length=3),
            nullable=False,
        ),
        sa.Column(
            "amount",
            sa.Numeric(precision=78, scale=0),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column(
            "payout_movement_id",
            sa.BigInteger(),
            nullable=True,
        ),
        sa.Column(
            "transaction_hash",
            sa.String(length=66),
            nullable=True,
        ),
        sa.Column(
            "block_number",
            sa.BigInteger(),
            nullable=True,
        ),
        sa.Column(
            "failure_reason",
            sa.String(length=500),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "amount > 0",
            name="ck_redemption_request_amount_positive",
        ),
        sa.ForeignKeyConstraint(
            ["currency"],
            ["reserve_accounts.currency"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["payout_movement_id"],
            ["fiat_movements.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint(
            "request_id",
        ),
    )

    op.create_index(
        op.f(
            "ix_redemption_requests_bank_address"
        ),
        "redemption_requests",
        ["bank_address"],
        unique=False,
    )

    op.create_index(
        op.f(
            "ix_redemption_requests_status"
        ),
        "redemption_requests",
        ["status"],
        unique=False,
    )

    op.create_index(
        op.f(
            "ix_redemption_requests_transaction_hash"
        ),
        "redemption_requests",
        ["transaction_hash"],
        unique=False,
    )

    op.create_table(
        "reserve_reconciliations",
        sa.Column(
            "id",
            sa.BigInteger(),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "currency",
            sa.String(length=3),
            nullable=False,
        ),
        sa.Column(
            "reported_balance",
            sa.Numeric(precision=78, scale=0),
            nullable=False,
        ),
        sa.Column(
            "ledger_balance",
            sa.Numeric(precision=78, scale=0),
            nullable=False,
        ),
        sa.Column(
            "difference",
            sa.Numeric(precision=78, scale=0),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column(
            "source_reference",
            sa.String(length=255),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["currency"],
            ["reserve_accounts.currency"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "id",
        ),
    )

    op.create_index(
        op.f(
            "ix_reserve_reconciliations_currency"
        ),
        "reserve_reconciliations",
        ["currency"],
        unique=False,
    )

    op.create_index(
        op.f(
            "ix_reserve_reconciliations_status"
        ),
        "reserve_reconciliations",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f(
            "ix_reserve_reconciliations_status"
        ),
        table_name="reserve_reconciliations",
    )

    op.drop_index(
        op.f(
            "ix_reserve_reconciliations_currency"
        ),
        table_name="reserve_reconciliations",
    )

    op.drop_table(
        "reserve_reconciliations"
    )

    op.drop_index(
        op.f(
            "ix_redemption_requests_transaction_hash"
        ),
        table_name="redemption_requests",
    )

    op.drop_index(
        op.f(
            "ix_redemption_requests_status"
        ),
        table_name="redemption_requests",
    )

    op.drop_index(
        op.f(
            "ix_redemption_requests_bank_address"
        ),
        table_name="redemption_requests",
    )

    op.drop_table(
        "redemption_requests"
    )

    op.drop_index(
        op.f(
            "ix_mint_requests_transaction_hash"
        ),
        table_name="mint_requests",
    )

    op.drop_index(
        op.f(
            "ix_mint_requests_status"
        ),
        table_name="mint_requests",
    )

    op.drop_index(
        op.f(
            "ix_mint_requests_bank_address"
        ),
        table_name="mint_requests",
    )

    op.drop_table(
        "mint_requests"
    )

    op.drop_index(
        op.f(
            "ix_fiat_movements_status"
        ),
        table_name="fiat_movements",
    )

    op.drop_index(
        op.f(
            "ix_fiat_movements_bank_address"
        ),
        table_name="fiat_movements",
    )

    op.drop_index(
        op.f(
            "ix_fiat_movements_currency"
        ),
        table_name="fiat_movements",
    )

    op.drop_index(
        op.f(
            "ix_fiat_movements_movement_type"
        ),
        table_name="fiat_movements",
    )

    op.drop_table(
        "fiat_movements"
    )

    op.drop_table(
        "reserve_accounts"
    )
