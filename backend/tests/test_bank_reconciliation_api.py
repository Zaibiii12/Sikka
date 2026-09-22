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


CURRENCY = "BQA"
ACCOUNT_ID = "BANK-RECON-API"

settings = get_settings()
client = TestClient(app)


def cleanup():
    with SessionLocal() as db:
        db.execute(
            delete(FiatMovement)
            .where(
                FiatMovement.currency
                == CURRENCY
            )
        )

        db.execute(
            delete(BankTransactionRecord)
            .where(
                BankTransactionRecord
                .account_id
                == ACCOUNT_ID
            )
        )

        db.execute(
            delete(BankAccountRecord)
            .where(
                BankAccountRecord
                .account_id
                == ACCOUNT_ID
            )
        )

        db.execute(
            delete(ReserveAccount)
            .where(
                ReserveAccount.currency
                == CURRENCY
            )
        )

        db.commit()


@pytest.fixture(autouse=True)
def state():
    cleanup()

    with SessionLocal() as db:
        initialize_reserve_account(
            db,
            currency=CURRENCY,
            source_type="BANK_ADAPTER",
        )

        db.commit()

    yield

    cleanup()


def _create_account():
    response = client.post(
        (
            f"{settings.api_prefix}"
            "/mock-bank/accounts"
        ),
        json={
            "account_id":
                ACCOUNT_ID,
            "name":
                "Reconciliation API Bank",
            "currency":
                CURRENCY,
        },
    )

    assert response.status_code == 201


def _create_settled_credit(
    transaction_id: str,
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
                ACCOUNT_ID,
            "direction":
                "CREDIT",
            "amount_micro":
                4_000_000,
            "currency":
                CURRENCY,
        },
    )

    assert response.status_code == 201

    assert client.post(
        (
            f"{settings.api_prefix}"
            "/mock-bank/transactions/"
            f"{transaction_id}/pending"
        )
    ).status_code == 200

    assert client.post(
        (
            f"{settings.api_prefix}"
            "/mock-bank/transactions/"
            f"{transaction_id}/settle"
        )
    ).status_code == 200


def test_clean_reconciliation_api():
    _create_account()

    transaction_id = (
        "RECON-API-CLEAN-001"
    )

    _create_settled_credit(
        transaction_id
    )

    response = client.post(
        (
            f"{settings.api_prefix}"
            "/treasury/bank-settlements/"
            f"{transaction_id}/ingest"
        ),
        json={
            "currency":
                CURRENCY,
        },
    )

    assert response.status_code == 201

    response = client.get(
        (
            f"{settings.api_prefix}"
            "/treasury/"
            "bank-reconciliation"
        ),
        params={
            "account_id":
                ACCOUNT_ID,
            "currency":
                CURRENCY,
        },
    )

    assert response.status_code == 200

    report = response.json()

    assert report["clean"] is True
    assert report["issue_count"] == 0


def test_missing_treasury_deposit_is_visible_via_api():
    _create_account()

    transaction_id = (
        "RECON-API-MISSING-001"
    )

    _create_settled_credit(
        transaction_id
    )

    response = client.get(
        (
            f"{settings.api_prefix}"
            "/treasury/"
            "bank-reconciliation"
        ),
        params={
            "account_id":
                ACCOUNT_ID,
            "currency":
                CURRENCY,
        },
    )

    assert response.status_code == 200

    codes = {
        item["code"]
        for item
        in response.json()["issues"]
    }

    assert (
        "MISSING_TREASURY_DEPOSIT"
        in codes
    )
