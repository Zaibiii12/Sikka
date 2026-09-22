import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

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


CURRENCY = "BRA"
ACCOUNT_ID = "REVERSAL-API-RESERVE"

BANK_ADDRESS = (
    "0x1EC30b4058188c2c14eA5"
    "AB2930d71911F38f6cB"
)

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


def _prepare_ingested_credit(
    transaction_id: str,
):
    response = client.post(
        (
            f"{settings.api_prefix}"
            "/mock-bank/accounts"
        ),
        json={
            "account_id":
                ACCOUNT_ID,
            "name":
                "Reversal API Reserve",
            "currency":
                CURRENCY,
        },
    )

    assert response.status_code == 201

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

    response = client.post(
        (
            f"{settings.api_prefix}"
            "/treasury/bank-settlements/"
            f"{transaction_id}/ingest"
        ),
        json={
            "currency":
                CURRENCY,
            "bank_address":
                BANK_ADDRESS,
        },
    )

    assert response.status_code == 201


def test_api_processes_safe_reversal():
    transaction_id = (
        "API-REVERSAL-SAFE-001"
    )

    _prepare_ingested_credit(
        transaction_id
    )

    response = client.post(
        (
            f"{settings.api_prefix}"
            "/mock-bank/transactions/"
            f"{transaction_id}/reverse"
        )
    )

    assert response.status_code == 200

    response = client.post(
        (
            f"{settings.api_prefix}"
            "/treasury/bank-reversals/"
            f"{transaction_id}/process"
        ),
        json={
            "currency":
                CURRENCY,
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["applied"] is True
    assert data["manual_review"] is False
    assert data["status"] == "VERIFIED"

    assert (
        data["reserve"][
            "verified_balance_micro"
        ]
        == "0"
    )

    assert (
        data["risk"]["mint_blocked"]
        is False
    )


def test_manual_review_reversal_blocks_mint():
    transaction_id = (
        "API-REVERSAL-RISK-001"
    )

    _prepare_ingested_credit(
        transaction_id
    )

    with SessionLocal() as db:
        reserve = db.scalar(
            select(ReserveAccount)
            .where(
                ReserveAccount.currency
                == CURRENCY
            )
        )

        assert reserve is not None

        reserve.reserved_balance = 3_500_000

        db.commit()

    assert client.post(
        (
            f"{settings.api_prefix}"
            "/mock-bank/transactions/"
            f"{transaction_id}/reverse"
        )
    ).status_code == 200

    response = client.post(
        (
            f"{settings.api_prefix}"
            "/treasury/bank-reversals/"
            f"{transaction_id}/process"
        ),
        json={
            "currency":
                CURRENCY,
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["applied"] is False
    assert data["manual_review"] is True

    risk = client.get(
        (
            f"{settings.api_prefix}"
            "/treasury/bank-reversals/"
            "risk"
        ),
        params={
            "currency":
                CURRENCY,
        },
    )

    assert risk.status_code == 200

    risk_data = risk.json()

    assert (
        risk_data["unresolved_count"]
        == 1
    )

    assert (
        risk_data["mint_blocked"]
        is True
    )

    mint = client.post(
        (
            f"{settings.api_prefix}"
            "/treasury/mint"
        ),
        json={
            "reference":
                "MINT-WHILE-REVERSAL-OPEN",
            "bank_address":
                BANK_ADDRESS,
            "amount":
                "0.100000",
            "currency":
                CURRENCY,
        },
    )

    assert mint.status_code == 400

    assert (
        "unresolved bank reversal"
        in mint.json()["detail"].lower()
    )


def test_manual_review_can_be_resolved_after_reservation_release():
    transaction_id = (
        "API-REVERSAL-RESOLVE-001"
    )

    _prepare_ingested_credit(
        transaction_id
    )

    with SessionLocal() as db:
        reserve = db.scalar(
            select(ReserveAccount)
            .where(
                ReserveAccount.currency
                == CURRENCY
            )
        )

        assert reserve is not None

        reserve.reserved_balance = 3_500_000
        db.commit()

    assert client.post(
        (
            f"{settings.api_prefix}"
            "/mock-bank/transactions/"
            f"{transaction_id}/reverse"
        )
    ).status_code == 200

    processed = client.post(
        (
            f"{settings.api_prefix}"
            "/treasury/bank-reversals/"
            f"{transaction_id}/process"
        ),
        json={
            "currency": CURRENCY,
        },
    )

    assert processed.status_code == 201

    movement_id = (
        processed.json()[
            "movement_id"
        ]
    )

    assert (
        processed.json()[
            "manual_review"
        ]
        is True
    )

    #
    # Simulate the conflicting reservation
    # being safely released by its owning
    # workflow.
    #
    with SessionLocal() as db:
        reserve = db.scalar(
            select(ReserveAccount)
            .where(
                ReserveAccount.currency
                == CURRENCY
            )
        )

        assert reserve is not None

        reserve.reserved_balance = 0
        db.commit()

    resolved = client.post(
        (
            f"{settings.api_prefix}"
            "/treasury/bank-reversals/"
            f"{movement_id}/resolve"
        ),
        json={
            "operator_reference":
                "OPS-TICKET-RESOLVE-001",
            "note":
                (
                    "Reservation released "
                    "after operational review."
                ),
        },
    )

    assert resolved.status_code == 201

    data = resolved.json()

    assert (
        data["reversal_movement_id"]
        == movement_id
    )

    assert (
        data["risk"]["unresolved_count"]
        == 0
    )

    assert (
        data["risk"]["mint_blocked"]
        is False
    )

    assert (
        data["reserve"][
            "verified_balance_micro"
        ]
        == "0"
    )
