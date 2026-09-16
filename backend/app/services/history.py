from __future__ import annotations

from decimal import Decimal

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.db.models import (
    BankRecord,
    ChainEvent,
    PaymentRecord,
    SettlementPayment,
    SettlementRecord,
    TokenTransfer,
)
from app.db.session import SessionLocal


def _decimal_to_int(value: Decimal | int) -> int:
    return int(value)


class HistoryService:
    def _session(self) -> Session:
        return SessionLocal()

    def events(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        event_name: str | None = None,
        contract_address: str | None = None,
    ) -> list[dict]:
        with self._session() as session:
            query = select(ChainEvent)

            if event_name:
                query = query.where(
                    ChainEvent.event_name == event_name
                )

            if contract_address:
                query = query.where(
                    ChainEvent.contract_address.ilike(
                        contract_address
                    )
                )

            query = (
                query
                .order_by(
                    desc(ChainEvent.block_number),
                    desc(ChainEvent.log_index),
                )
                .offset(offset)
                .limit(limit)
            )

            rows = session.scalars(query).all()

            return [
                {
                    "id": row.id,
                    "chain_id": row.chain_id,
                    "contract_name": row.contract_name,
                    "contract_address": row.contract_address,
                    "event_name": row.event_name,
                    "block_number": row.block_number,
                    "block_hash": row.block_hash,
                    "transaction_hash": row.transaction_hash,
                    "transaction_index": row.transaction_index,
                    "log_index": row.log_index,
                    "block_timestamp": row.block_timestamp.isoformat(),
                    "decoded_args": row.decoded_args,
                    "indexed_at": row.indexed_at.isoformat(),
                }
                for row in rows
            ]

    def payments(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        from_address: str | None = None,
        to_address: str | None = None,
    ) -> list[dict]:
        with self._session() as session:
            query = select(PaymentRecord)

            if from_address:
                query = query.where(
                    PaymentRecord.from_address.ilike(
                        from_address
                    )
                )

            if to_address:
                query = query.where(
                    PaymentRecord.to_address.ilike(
                        to_address
                    )
                )

            query = (
                query
                .order_by(
                    desc(PaymentRecord.block_number)
                )
                .offset(offset)
                .limit(limit)
            )

            rows = session.scalars(query).all()

            return [
                self._payment_dict(row)
                for row in rows
            ]

    def payment(
        self,
        payment_id: str,
    ) -> dict | None:
        with self._session() as session:
            row = session.get(
                PaymentRecord,
                payment_id,
            )

            if row is None:
                return None

            result = self._payment_dict(row)

            settlement_link = session.scalar(
                select(SettlementPayment)
                .where(
                    SettlementPayment.payment_id
                    == payment_id
                )
            )

            result["settled"] = (
                settlement_link is not None
            )

            result["settlement_batch_id"] = (
                settlement_link.batch_id
                if settlement_link
                else None
            )

            return result

    @staticmethod
    def _payment_dict(
        row: PaymentRecord,
    ) -> dict:
        return {
            "payment_id": row.payment_id,
            "from_address": row.from_address,
            "to_address": row.to_address,
            "amount": _decimal_to_int(
                row.amount
            ),
            "nonce": row.nonce,
            "transaction_hash": row.transaction_hash,
            "block_number": row.block_number,
            "block_timestamp": (
                row.block_timestamp.isoformat()
            ),
        }

    def settlements(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        with self._session() as session:
            query = (
                select(SettlementRecord)
                .order_by(
                    desc(
                        SettlementRecord
                        .block_number
                    )
                )
                .offset(offset)
                .limit(limit)
            )

            rows = session.scalars(query).all()

            return [
                self._settlement_dict(
                    session,
                    row,
                )
                for row in rows
            ]

    def settlement(
        self,
        batch_id: str,
    ) -> dict | None:
        with self._session() as session:
            row = session.get(
                SettlementRecord,
                batch_id,
            )

            if row is None:
                return None

            return self._settlement_dict(
                session,
                row,
            )

    @staticmethod
    def _settlement_dict(
        session: Session,
        row: SettlementRecord,
    ) -> dict:
        payment_ids = session.scalars(
            select(
                SettlementPayment.payment_id
            )
            .where(
                SettlementPayment.batch_id
                == row.batch_id
            )
        ).all()

        return {
            "batch_id": row.batch_id,
            "payment_count": row.payment_count,
            "payment_ids": list(
                payment_ids
            ),
            "settled_by": row.settled_by,
            "transaction_hash": row.transaction_hash,
            "block_number": row.block_number,
            "settled_at": row.settled_at.isoformat(),
        }

    def transfers(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        address: str | None = None,
    ) -> list[dict]:
        with self._session() as session:
            query = select(TokenTransfer)

            if address:
                query = query.where(
                    (
                        TokenTransfer.from_address.ilike(
                            address
                        )
                    )
                    |
                    (
                        TokenTransfer.to_address.ilike(
                            address
                        )
                    )
                )

            query = (
                query
                .order_by(
                    desc(TokenTransfer.block_number),
                    desc(TokenTransfer.log_index),
                )
                .offset(offset)
                .limit(limit)
            )

            rows = session.scalars(query).all()

            return [
                {
                    "from_address": row.from_address,
                    "to_address": row.to_address,
                    "amount": _decimal_to_int(
                        row.amount
                    ),
                    "transaction_hash": row.transaction_hash,
                    "block_number": row.block_number,
                    "log_index": row.log_index,
                    "block_timestamp": (
                        row.block_timestamp.isoformat()
                    ),
                }
                for row in rows
            ]

    def banks(
        self,
    ) -> list[dict]:
        with self._session() as session:
            rows = session.scalars(
                select(BankRecord)
                .order_by(
                    BankRecord.registered_at
                )
            ).all()

            return [
                {
                    "address": row.address,
                    "name": row.name,
                    "active": row.active,
                    "registered_at": (
                        row.registered_at.isoformat()
                    ),
                    "last_updated_block": (
                        row.last_updated_block
                    ),
                }
                for row in rows
            ]
