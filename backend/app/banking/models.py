from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class BankTransactionStatus(StrEnum):
    INITIATED = "INITIATED"
    PENDING = "PENDING"
    SETTLED = "SETTLED"
    FAILED = "FAILED"
    REVERSED = "REVERSED"


class BankTransactionDirection(StrEnum):
    CREDIT = "CREDIT"
    DEBIT = "DEBIT"


@dataclass(slots=True)
class BankAccount:
    account_id: str
    name: str
    currency: str
    active: bool
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class BankTransaction:
    transaction_id: str
    account_id: str
    direction: BankTransactionDirection
    currency: str
    amount_micro: int
    status: BankTransactionStatus
    created_at: datetime
    updated_at: datetime
    settled_at: datetime | None = None
