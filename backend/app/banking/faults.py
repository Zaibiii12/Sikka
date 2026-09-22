from dataclasses import replace
from enum import StrEnum

from app.banking.base import BankAdapter
from app.banking.models import (
    BankTransaction,
    BankTransactionDirection,
    BankTransactionStatus,
)


class BankFaultMode(StrEnum):
    NONE = "NONE"
    UNAVAILABLE = "UNAVAILABLE"
    STALE_STATUS = "STALE_STATUS"
    WRONG_CURRENCY = "WRONG_CURRENCY"
    WRONG_DIRECTION = "WRONG_DIRECTION"
    NEGATIVE_AMOUNT = "NEGATIVE_AMOUNT"
    OMIT_LIST = "OMIT_LIST"
    DUPLICATE_LIST = "DUPLICATE_LIST"


class SimulatedBankFailure(
    RuntimeError
):
    """
    Failure injected by the development/test
    bank fault simulator.

    This represents transport/provider failure,
    not a valid business-state response.
    """


class FaultInjectingBankAdapter(
    BankAdapter
):
    """
    Adversarial BankAdapter wrapper.

    The wrapped adapter remains unchanged.
    Faults are applied only to data observed by
    the caller.

    This makes it possible to verify that
    Treasury fails closed when external bank
    information is unavailable, stale, malformed,
    missing, or duplicated.
    """

    def __init__(
        self,
        wrapped: BankAdapter,
        *,
        mode: BankFaultMode
        = BankFaultMode.NONE,
        wrong_currency: str = "ZZZ",
    ):
        self._wrapped = wrapped
        self.mode = mode
        self.wrong_currency = (
            wrong_currency.strip().upper()
        )

    def get_transaction(
        self,
        transaction_id: str,
    ) -> BankTransaction | None:
        if (
            self.mode
            == BankFaultMode.UNAVAILABLE
        ):
            raise SimulatedBankFailure(
                "Simulated bank provider "
                "is unavailable."
            )

        transaction = (
            self._wrapped.get_transaction(
                transaction_id
            )
        )

        if transaction is None:
            return None

        return self._mutate_transaction(
            transaction
        )

    def list_transactions(
        self,
        account_id: str | None = None,
    ) -> list[BankTransaction]:
        if (
            self.mode
            == BankFaultMode.UNAVAILABLE
        ):
            raise SimulatedBankFailure(
                "Simulated bank provider "
                "is unavailable."
            )

        transactions = list(
            self._wrapped.list_transactions(
                account_id=account_id
            )
        )

        if (
            self.mode
            == BankFaultMode.OMIT_LIST
        ):
            return []

        mutated = [
            self._mutate_transaction(
                transaction
            )
            for transaction
            in transactions
        ]

        if (
            self.mode
            == BankFaultMode.DUPLICATE_LIST
            and mutated
        ):
            return [
                *mutated,
                mutated[0],
            ]

        return mutated

    def _mutate_transaction(
        self,
        transaction: BankTransaction,
    ) -> BankTransaction:
        if (
            self.mode
            == BankFaultMode.STALE_STATUS
        ):
            return replace(
                transaction,
                status=(
                    BankTransactionStatus
                    .PENDING
                ),
            )

        if (
            self.mode
            == BankFaultMode.WRONG_CURRENCY
        ):
            return replace(
                transaction,
                currency=self.wrong_currency,
            )

        if (
            self.mode
            == BankFaultMode.WRONG_DIRECTION
        ):
            return replace(
                transaction,
                direction=(
                    BankTransactionDirection
                    .DEBIT
                ),
            )

        if (
            self.mode
            == BankFaultMode.NEGATIVE_AMOUNT
        ):
            return replace(
                transaction,
                amount_micro=-1,
            )

        return transaction
