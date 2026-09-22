from datetime import (
    datetime,
    timezone,
)
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.banking.base import BankAdapter
from app.banking.mock import (
    DuplicateBankTransactionError,
    InvalidBankTransactionError,
    InvalidBankTransactionTransitionError,
    UnknownBankTransactionError,
)
from app.banking.models import (
    BankAccount,
    BankTransaction,
    BankTransactionDirection,
    BankTransactionStatus,
)
from app.db.bank_models import (
    BankAccountRecord,
    BankTransactionRecord,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class DatabaseMockBankAdapter(
    BankAdapter
):
    def __init__(
        self,
        db: Session,
    ) -> None:
        self.db = db

    def create_account(
        self,
        *,
        account_id: str,
        name: str,
        currency: str = "USD",
    ) -> BankAccount:
        account_id = account_id.strip()
        name = name.strip()
        currency = currency.strip().upper()

        if not account_id:
            raise InvalidBankTransactionError(
                "Account ID is required."
            )

        if not name:
            raise InvalidBankTransactionError(
                "Account name is required."
            )

        if not currency:
            raise InvalidBankTransactionError(
                "Currency is required."
            )

        if (
            self.db.get(
                BankAccountRecord,
                account_id,
            )
            is not None
        ):
            raise InvalidBankTransactionError(
                "Bank account already exists."
            )

        now = _now()

        row = BankAccountRecord(
            account_id=account_id,
            name=name,
            currency=currency,
            active=True,
            created_at=now,
            updated_at=now,
        )

        self.db.add(row)
        self.db.flush()

        return self._account(row)

    def get_account(
        self,
        account_id: str,
    ) -> BankAccount | None:
        row = self.db.get(
            BankAccountRecord,
            account_id,
        )

        if row is None:
            return None

        return self._account(row)

    def create_transaction(
        self,
        *,
        transaction_id: str,
        account_id: str,
        direction: (
            BankTransactionDirection
        ),
        amount_micro: int,
        currency: str = "USD",
    ) -> BankTransaction:
        transaction_id = (
            transaction_id.strip()
        )

        account_id = account_id.strip()
        currency = currency.strip().upper()

        if not transaction_id:
            raise InvalidBankTransactionError(
                "Transaction ID is required."
            )

        if amount_micro <= 0:
            raise InvalidBankTransactionError(
                "Bank transaction amount "
                "must be positive."
            )

        account = self.db.get(
            BankAccountRecord,
            account_id,
        )

        if account is None:
            raise InvalidBankTransactionError(
                "Bank account not found."
            )

        if not account.active:
            raise InvalidBankTransactionError(
                "Bank account is inactive."
            )

        if account.currency != currency:
            raise InvalidBankTransactionError(
                "Transaction currency does "
                "not match bank account."
            )

        if (
            self.db.get(
                BankTransactionRecord,
                transaction_id,
            )
            is not None
        ):
            raise (
                DuplicateBankTransactionError(
                    "Bank transaction already "
                    "exists."
                )
            )

        now = _now()

        row = BankTransactionRecord(
            transaction_id=transaction_id,
            account_id=account_id,
            direction=direction.value,
            currency=currency,
            amount_micro=Decimal(
                amount_micro
            ),
            status=(
                BankTransactionStatus
                .INITIATED
                .value
            ),
            created_at=now,
            updated_at=now,
            settled_at=None,
        )

        self.db.add(row)
        self.db.flush()

        return self._transaction(row)

    def get_transaction(
        self,
        transaction_id: str,
    ) -> BankTransaction | None:
        row = self.db.get(
            BankTransactionRecord,
            transaction_id,
        )

        if row is None:
            return None

        return self._transaction(row)

    def list_transactions(
        self,
        *,
        account_id: str | None = None,
    ) -> list[BankTransaction]:
        stmt = select(
            BankTransactionRecord
        )

        if account_id is not None:
            stmt = stmt.where(
                BankTransactionRecord
                .account_id
                == account_id
            )

        stmt = stmt.order_by(
            BankTransactionRecord
            .created_at.asc()
        )

        rows = self.db.scalars(
            stmt
        ).all()

        return [
            self._transaction(row)
            for row in rows
        ]

    def mark_pending(
        self,
        transaction_id: str,
    ) -> BankTransaction:
        return self._transition(
            transaction_id,
            target=(
                BankTransactionStatus
                .PENDING
            ),
            allowed={
                BankTransactionStatus
                .INITIATED,
            },
        )

    def settle(
        self,
        transaction_id: str,
    ) -> BankTransaction:
        return self._transition(
            transaction_id,
            target=(
                BankTransactionStatus
                .SETTLED
            ),
            allowed={
                BankTransactionStatus
                .PENDING,
            },
        )

    def fail(
        self,
        transaction_id: str,
    ) -> BankTransaction:
        return self._transition(
            transaction_id,
            target=(
                BankTransactionStatus
                .FAILED
            ),
            allowed={
                BankTransactionStatus
                .INITIATED,
                BankTransactionStatus
                .PENDING,
            },
        )

    def reverse(
        self,
        transaction_id: str,
    ) -> BankTransaction:
        return self._transition(
            transaction_id,
            target=(
                BankTransactionStatus
                .REVERSED
            ),
            allowed={
                BankTransactionStatus
                .SETTLED,
            },
        )

    def _transition(
        self,
        transaction_id: str,
        *,
        target: BankTransactionStatus,
        allowed: set[
            BankTransactionStatus
        ],
    ) -> BankTransaction:
        stmt = (
            select(
                BankTransactionRecord
            )
            .where(
                BankTransactionRecord
                .transaction_id
                == transaction_id
            )
            .with_for_update()
        )

        row = self.db.scalar(stmt)

        if row is None:
            raise (
                UnknownBankTransactionError(
                    "Bank transaction "
                    "not found."
                )
            )

        current = (
            BankTransactionStatus(
                row.status
            )
        )

        if current not in allowed:
            raise (
                InvalidBankTransactionTransitionError(
                    "Cannot transition "
                    "bank transaction "
                    f"from {current} "
                    f"to {target}."
                )
            )

        now = _now()

        row.status = target.value
        row.updated_at = now

        if (
            target
            == BankTransactionStatus.SETTLED
        ):
            row.settled_at = now

        self.db.flush()

        return self._transaction(row)

    @staticmethod
    def _account(
        row: BankAccountRecord,
    ) -> BankAccount:
        return BankAccount(
            account_id=row.account_id,
            name=row.name,
            currency=row.currency,
            active=row.active,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    @staticmethod
    def _transaction(
        row: BankTransactionRecord,
    ) -> BankTransaction:
        return BankTransaction(
            transaction_id=(
                row.transaction_id
            ),
            account_id=row.account_id,
            direction=(
                BankTransactionDirection(
                    row.direction
                )
            ),
            currency=row.currency,
            amount_micro=int(
                row.amount_micro
            ),
            status=(
                BankTransactionStatus(
                    row.status
                )
            ),
            created_at=row.created_at,
            updated_at=row.updated_at,
            settled_at=row.settled_at,
        )
