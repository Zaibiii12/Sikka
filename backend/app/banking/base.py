from abc import ABC, abstractmethod

from app.banking.models import BankTransaction


class BankAdapter(ABC):
    @abstractmethod
    def get_transaction(
        self,
        transaction_id: str,
    ) -> BankTransaction | None:
        """Return one external bank transaction."""

    @abstractmethod
    def list_transactions(
        self,
        *,
        account_id: str | None = None,
    ) -> list[BankTransaction]:
        """Return transactions visible from the bank."""
