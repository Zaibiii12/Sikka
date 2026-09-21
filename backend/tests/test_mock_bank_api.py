import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.config import get_settings
from app.db.bank_models import (
    BankAccountRecord,
    BankTransactionRecord,
)
from app.db.models import (
    FiatMovement,
    ReserveAccount,
)
from app.db.session import SessionLocal
from app.main import app
from app.services.treasury import (
    initialize_reserve_account,
)


TEST_CURRENCY = "BAP"
TEST_ACCOUNT_ID = "API-BANK-RESERVE"

settings = get_settings()
client = TestClient(app)


def cleanup() -> None:
    with SessionLocal() as db:
        db.execute(
            delete(FiatMovement)
            .where(
                FiatMovement.currency
                == TEST_CURRENCY
            )
        )

        db.execute(
            delete(BankTransactionRecord)
            .where(
                BankTransactionRecord.account_id
                == TEST_ACCOUNT_ID
            )
        )

        db.execute(
            delete(BankAccountRecord)
            .where(
                BankAccountRecord.account_id
                == TEST_ACCOUNT_ID
            )
        )

        db.execute(
            delete(ReserveAccount)
            .where(
                ReserveAccount.currency
                == TEST_CURRENCY
            )
        )

        db.commit()


@pytest.fixture(autouse=True)
def mock_bank_api_state():
    cleanup()

    with SessionLocal() as db:
        initialize_reserve_account(
            db,
            currency=TEST_CURRENCY,
            source_type="BANK_ADAPTER",
        )

        db.commit()

    yield

    cleanup()


def create_bank_account() -> None:
    response = client.post(
        (
            f"{settings.api_prefix}"
            "/mock-bank/accounts"
        ),
        json={
            "account_id":
                TEST_ACCOUNT_ID,
            "name":
                "API Mock Reserve",
            "currency":
                TEST_CURRENCY,
        },
    )

    assert response.status_code == 201


def create_credit(
    transaction_id: str,
    *,
    amount_micro: int = 1_000_000,
):
    response = client.post(
        (
            f"{settings.api_prefix}"
            "/mock-bank/transactions"
        ),
        json={
            "transaction_id":
                transaction_id,
            "account_id":
                TEST_ACCOUNT_ID,
            "direction":
                "CREDIT",
            "amount_micro":
                amount_micro,
            "currency":
                TEST_CURRENCY,
        },
    )

    assert response.status_code == 201

    return response


def test_bank_to_treasury_http_flow():
    create_bank_account()

    create_credit(
        "API-BANK-TXN-001",
        amount_micro=3_000_000,
    )

    pending = client.post(
        (
            f"{settings.api_prefix}"
            "/mock-bank/transactions/"
            "API-BANK-TXN-001/pending"
        )
    )

    assert pending.status_code == 200

    assert (
        pending.json()["status"]
        == "PENDING"
    )

    settled = client.post(
        (
            f"{settings.api_prefix}"
            "/mock-bank/transactions/"
            "API-BANK-TXN-001/settle"
        )
    )

    assert settled.status_code == 200

    assert (
        settled.json()["status"]
        == "SETTLED"
    )

    ingested = client.post(
        (
            f"{settings.api_prefix}"
            "/treasury/bank-settlements/"
            "API-BANK-TXN-001/ingest"
        ),
        json={
            "currency":
                TEST_CURRENCY,
        },
    )

    assert ingested.status_code == 201

    data = ingested.json()

    assert (
        data["bank_transaction_id"]
        == "API-BANK-TXN-001"
    )

    assert (
        data["reserve"][
            "verified_balance_micro"
        ]
        == "3000000"
    )

    duplicate = client.post(
        (
            f"{settings.api_prefix}"
            "/treasury/bank-settlements/"
            "API-BANK-TXN-001/ingest"
        ),
        json={
            "currency":
                TEST_CURRENCY,
        },
    )

    assert duplicate.status_code == 409

    reserve = client.get(
        (
            f"{settings.api_prefix}"
            "/treasury/reserve"
        ),
        params={
            "currency":
                TEST_CURRENCY,
        },
    )

    assert reserve.status_code == 200

    assert (
        reserve.json()[
            "verified_balance_micro"
        ]
        == "3000000"
    )


def test_pending_transaction_cannot_back_reserve():
    create_bank_account()

    create_credit(
        "API-BANK-PENDING-001"
    )

    pending = client.post(
        (
            f"{settings.api_prefix}"
            "/mock-bank/transactions/"
            "API-BANK-PENDING-001/"
            "pending"
        )
    )

    assert pending.status_code == 200

    response = client.post(
        (
            f"{settings.api_prefix}"
            "/treasury/bank-settlements/"
            "API-BANK-PENDING-001/"
            "ingest"
        ),
        json={
            "currency":
                TEST_CURRENCY,
        },
    )

    assert response.status_code == 409

    reserve = client.get(
        (
            f"{settings.api_prefix}"
            "/treasury/reserve"
        ),
        params={
            "currency":
                TEST_CURRENCY,
        },
    )

    assert reserve.status_code == 200

    assert (
        reserve.json()[
            "verified_balance_micro"
        ]
        == "0"
    )


def test_invalid_bank_transition_returns_409():
    create_bank_account()

    create_credit(
        "API-BANK-STATE-001"
    )

    response = client.post(
        (
            f"{settings.api_prefix}"
            "/mock-bank/transactions/"
            "API-BANK-STATE-001/"
            "settle"
        )
    )

    assert response.status_code == 409

    stored = client.get(
        (
            f"{settings.api_prefix}"
            "/mock-bank/transactions/"
            "API-BANK-STATE-001"
        )
    )

    assert stored.status_code == 200

    assert (
        stored.json()["status"]
        == "INITIATED"
    )


def test_transaction_lookup_and_list():
    create_bank_account()

    create_credit(
        "API-BANK-LIST-001"
    )

    lookup = client.get(
        (
            f"{settings.api_prefix}"
            "/mock-bank/transactions/"
            "API-BANK-LIST-001"
        )
    )

    assert lookup.status_code == 200

    assert (
        lookup.json()[
            "transaction_id"
        ]
        == "API-BANK-LIST-001"
    )

    listing = client.get(
        (
            f"{settings.api_prefix}"
            "/mock-bank/transactions"
        ),
        params={
            "account_id":
                TEST_ACCOUNT_ID,
        },
    )

    assert listing.status_code == 200

    data = listing.json()

    assert data["count"] == 1

    assert (
        data["items"][0][
            "transaction_id"
        ]
        == "API-BANK-LIST-001"
    )
