from dataclasses import replace
from datetime import datetime, timezone

from app.banking.base import BankAdapter
from app.banking.models import (
    BankTransaction,
    BankTransactionDirection,
    BankTransactionStatus,
)


class BankAdapterError(Exception):
    pass


class DuplicateBankTransactionError(
    BankAdapterError
):
    pass


class UnknownBankTransactionError(
    BankAdapterError
):
    pass


class InvalidBankTransactionError(
    BankAdapterError
):
    pass


class InvalidBankTransactionTransitionError(
    BankAdapterError
):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


class MockBankAdapter(BankAdapter):
    def __init__(self) -> None:
        self._transactions: dict[
            str,
            BankTransaction,
        ] = {}

    def create_transaction(
        self,
        *,
        transaction_id: str,
        account_id: str,
        direction: BankTransactionDirection,
        amount_micro: int,
        currency: str = "USD",
    ) -> BankTransaction:
        transaction_id = transaction_id.strip()
        account_id = account_id.strip()
        currency = currency.strip().upper()

        if not transaction_id:
            raise InvalidBankTransactionError(
                "Transaction ID is required."
            )

        if not account_id:
            raise InvalidBankTransactionError(
                "Account ID is required."
            )

        if amount_micro <= 0:
            raise InvalidBankTransactionError(
                "Bank transaction amount must be positive."
            )

        if not currency:
            raise InvalidBankTransactionError(
                "Currency is required."
            )

        if transaction_id in self._transactions:
            raise DuplicateBankTransactionError(
                "Bank transaction already exists."
            )

        now = _now()

        row = BankTransaction(
            transaction_id=transaction_id,
            account_id=account_id,
            direction=direction,
            currency=currency,
            amount_micro=amount_micro,
            status=BankTransactionStatus.INITIATED,
            created_at=now,
            updated_at=now,
        )

        self._transactions[transaction_id] = row

        return replace(row)

    def get_transaction(
        self,
        transaction_id: str,
    ) -> BankTransaction | None:
        row = self._transactions.get(
            transaction_id
        )

        if row is None:
            return None

        return replace(row)

    def list_transactions(
        self,
        *,
        account_id: str | None = None,
    ) -> list[BankTransaction]:
        rows = list(
            self._transactions.values()
        )

        if account_id is not None:
            rows = [
                row
                for row in rows
                if row.account_id == account_id
            ]

        rows.sort(
            key=lambda row: row.created_at
        )

        return [
            replace(row)
            for row in rows
        ]

    def mark_pending(
        self,
        transaction_id: str,
    ) -> BankTransaction:
        return self._transition(
            transaction_id,
            target=BankTransactionStatus.PENDING,
            allowed={
                BankTransactionStatus.INITIATED,
            },
        )

    def settle(
        self,
        transaction_id: str,
    ) -> BankTransaction:
        return self._transition(
            transaction_id,
            target=BankTransactionStatus.SETTLED,
            allowed={
                BankTransactionStatus.PENDING,
            },
        )

    def fail(
        self,
        transaction_id: str,
    ) -> BankTransaction:
        return self._transition(
            transaction_id,
            target=BankTransactionStatus.FAILED,
            allowed={
                BankTransactionStatus.INITIATED,
                BankTransactionStatus.PENDING,
            },
        )

    def reverse(
        self,
        transaction_id: str,
    ) -> BankTransaction:
        return self._transition(
            transaction_id,
            target=BankTransactionStatus.REVERSED,
            allowed={
                BankTransactionStatus.SETTLED,
            },
        )

    def _transition(
        self,
        transaction_id: str,
        *,
        target: BankTransactionStatus,
        allowed: set[BankTransactionStatus],
    ) -> BankTransaction:
        row = self._transactions.get(
            transaction_id
        )

        if row is None:
            raise UnknownBankTransactionError(
                "Bank transaction not found."
            )

        if row.status not in allowed:
            raise InvalidBankTransactionTransitionError(
                "Cannot transition bank transaction from "
                f"{row.status} to {target}."
            )

        now = _now()

        row.status = target
        row.updated_at = now

        if target == BankTransactionStatus.SETTLED:
            row.settled_at = now

        self._transactions[transaction_id] = row

        return replace(row)
