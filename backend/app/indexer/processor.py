from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.dialects.postgresql import (
    insert,
)
from sqlalchemy.orm import Session
from web3 import Web3

from app.core.contracts import (
    get_contracts,
)
from app.db.models import (
    BankRecord,
    ChainEvent,
    PaymentRecord,
    SettlementPayment,
    SettlementRecord,
    TokenTransfer,
)
from app.indexer.events import (
    EventDefinition,
)
from app.indexer.utils import (
    normalize_json,
    utc_datetime,
)


class EventProcessor:
    def __init__(self) -> None:
        self.contracts = (
            get_contracts()
        )

    def process(
        self,
        *,
        session: Session,
        definition: EventDefinition,
        args: dict[str, Any],
        log: Any,
        block_timestamp: datetime,
        chain_id: int,
    ) -> None:
        normalized_args = (
            normalize_json(args)
        )

        self._store_chain_event(
            session=session,
            definition=definition,
            args=normalized_args,
            log=log,
            block_timestamp=(
                block_timestamp
            ),
            chain_id=chain_id,
        )

        key = (
            definition.contract_name,
            definition.event_name,
        )

        if key == (
            "PaymentProcessor",
            "PaymentSubmitted",
        ):
            self._payment_submitted(
                session=session,
                args=args,
                log=log,
                block_timestamp=(
                    block_timestamp
                ),
            )

        elif key == (
            "SettlementEngine",
            "SettlementBatchCreated",
        ):
            self._settlement_created(
                session=session,
                args=args,
                log=log,
            )

        elif key == (
            "BankRegistry",
            "BankRegistered",
        ):
            self._bank_registered(
                session=session,
                args=args,
                log=log,
                block_timestamp=(
                    block_timestamp
                ),
            )

        elif key == (
            "BankRegistry",
            "BankDeactivated",
        ):
            self._bank_status(
                session=session,
                args=args,
                log=log,
                active=False,
            )

        elif key == (
            "BankRegistry",
            "BankReactivated",
        ):
            self._bank_status(
                session=session,
                args=args,
                log=log,
                active=True,
            )

        elif key == (
            "PrivateUSD",
            "Transfer",
        ):
            self._token_transfer(
                session=session,
                args=args,
                log=log,
                block_timestamp=(
                    block_timestamp
                ),
            )

    @staticmethod
    def _store_chain_event(
        *,
        session: Session,
        definition: EventDefinition,
        args: dict[str, Any],
        log: Any,
        block_timestamp: datetime,
        chain_id: int,
    ) -> None:
        statement = (
            insert(ChainEvent)
            .values(
                chain_id=chain_id,
                contract_name=(
                    definition
                    .contract_name
                ),
                contract_address=(
                    definition
                    .contract
                    .address
                ),
                event_name=(
                    definition
                    .event_name
                ),
                block_number=(
                    log["blockNumber"]
                ),
                block_hash=Web3.to_hex(
                    log["blockHash"]
                ),
                transaction_hash=(
                    Web3.to_hex(
                        log[
                            "transactionHash"
                        ]
                    )
                ),
                transaction_index=(
                    log[
                        "transactionIndex"
                    ]
                ),
                log_index=(
                    log["logIndex"]
                ),
                block_timestamp=(
                    block_timestamp
                ),
                decoded_args=args,
            )
            .on_conflict_do_nothing(
                constraint=(
                    "uq_chain_event_log"
                )
            )
        )

        session.execute(statement)

    @staticmethod
    def _payment_submitted(
        *,
        session: Session,
        args: dict[str, Any],
        log: Any,
        block_timestamp: datetime,
    ) -> None:
        payment_id = Web3.to_hex(
            args["paymentId"]
        )

        statement = (
            insert(PaymentRecord)
            .values(
                payment_id=payment_id,
                from_address=args[
                    "from"
                ],
                to_address=args[
                    "to"
                ],
                amount=Decimal(
                    args["amount"]
                ),
                nonce=args["nonce"],
                transaction_hash=(
                    Web3.to_hex(
                        log[
                            "transactionHash"
                        ]
                    )
                ),
                block_number=(
                    log["blockNumber"]
                ),
                block_timestamp=(
                    block_timestamp
                ),
            )
            .on_conflict_do_nothing(
                index_elements=[
                    PaymentRecord.payment_id
                ]
            )
        )

        session.execute(statement)

    def _settlement_created(
        self,
        *,
        session: Session,
        args: dict[str, Any],
        log: Any,
    ) -> None:
        batch_id_bytes = args[
            "batchId"
        ]

        batch_id = Web3.to_hex(
            batch_id_bytes
        )

        (
            payment_ids,
            settled_at,
            settled_by,
        ) = (
            self.contracts
            .settlement_engine
            .functions
            .getBatch(
                batch_id_bytes
            )
            .call()
        )

        settlement_statement = (
            insert(SettlementRecord)
            .values(
                batch_id=batch_id,
                payment_count=args[
                    "paymentCount"
                ],
                settled_by=(
                    settled_by
                ),
                transaction_hash=(
                    Web3.to_hex(
                        log[
                            "transactionHash"
                        ]
                    )
                ),
                block_number=(
                    log["blockNumber"]
                ),
                settled_at=utc_datetime(
                    settled_at
                ),
            )
            .on_conflict_do_nothing(
                index_elements=[
                    SettlementRecord
                    .batch_id
                ]
            )
        )

        session.execute(
            settlement_statement
        )

        for payment_id_bytes in (
            payment_ids
        ):
            payment_id = Web3.to_hex(
                payment_id_bytes
            )

            link_statement = (
                insert(
                    SettlementPayment
                )
                .values(
                    batch_id=batch_id,
                    payment_id=payment_id,
                )
                .on_conflict_do_nothing()
            )

            session.execute(
                link_statement
            )

    @staticmethod
    def _bank_registered(
        *,
        session: Session,
        args: dict[str, Any],
        log: Any,
        block_timestamp: datetime,
    ) -> None:
        address = args[
            "bankAddress"
        ]

        statement = (
            insert(BankRecord)
            .values(
                address=address,
                name=args["name"],
                active=True,
                registered_at=(
                    block_timestamp
                ),
                last_updated_block=(
                    log["blockNumber"]
                ),
            )
            .on_conflict_do_update(
                index_elements=[
                    BankRecord.address
                ],
                set_={
                    "name": args[
                        "name"
                    ],
                    "active": True,
                    "last_updated_block": (
                        log[
                            "blockNumber"
                        ]
                    ),
                },
            )
        )

        session.execute(statement)

    @staticmethod
    def _bank_status(
        *,
        session: Session,
        args: dict[str, Any],
        log: Any,
        active: bool,
    ) -> None:
        address = args[
            "bankAddress"
        ]

        statement = (
            insert(BankRecord)
            .values(
                address=address,
                name="",
                active=active,
                registered_at=(
                    datetime.fromtimestamp(
                        0,
                        tz=(
                            block_timestamp_tz()
                        ),
                    )
                ),
                last_updated_block=(
                    log["blockNumber"]
                ),
            )
            .on_conflict_do_update(
                index_elements=[
                    BankRecord.address
                ],
                set_={
                    "active": active,
                    "last_updated_block": (
                        log[
                            "blockNumber"
                        ]
                    ),
                },
            )
        )

        session.execute(statement)

    @staticmethod
    def _token_transfer(
        *,
        session: Session,
        args: dict[str, Any],
        log: Any,
        block_timestamp: datetime,
    ) -> None:
        statement = (
            insert(TokenTransfer)
            .values(
                from_address=args[
                    "from"
                ],
                to_address=args[
                    "to"
                ],
                amount=Decimal(
                    args["value"]
                ),
                transaction_hash=(
                    Web3.to_hex(
                        log[
                            "transactionHash"
                        ]
                    )
                ),
                block_number=(
                    log["blockNumber"]
                ),
                log_index=(
                    log["logIndex"]
                ),
                block_timestamp=(
                    block_timestamp
                ),
            )
            .on_conflict_do_nothing(
                constraint=(
                    "uq_token_transfer_log"
                )
            )
        )

        session.execute(statement)


def block_timestamp_tz():
    from datetime import UTC

    return UTC
