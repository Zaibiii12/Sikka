import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.config import get_settings
from app.db.models import (
    FiatMovement,
    ReserveAccount,
)
from app.db.session import SessionLocal
from app.main import app
from app.services.treasury import (
    initialize_reserve_account,
)


TEST_CURRENCY = "API"
TEST_REFERENCE = (
    "API-TREASURY-DEPOSIT-001"
)

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
            delete(ReserveAccount)
            .where(
                ReserveAccount.currency
                == TEST_CURRENCY
            )
        )

        db.commit()


@pytest.fixture(autouse=True)
def treasury_api_state():
    cleanup()

    with SessionLocal() as db:
        initialize_reserve_account(
            db,
            currency=TEST_CURRENCY,
            source_type="SIMULATED",
        )

        db.commit()

    yield

    cleanup()


def test_get_reserve():
    response = client.get(
        (
            f"{settings.api_prefix}"
            "/treasury/reserve"
        ),
        params={
            "currency":
                TEST_CURRENCY,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert (
        data["currency"]
        == TEST_CURRENCY
    )

    assert (
        data[
            "verified_balance_micro"
        ]
        == "0"
    )


def test_simulated_deposit():
    response = client.post(
        (
            f"{settings.api_prefix}"
            "/treasury/simulated/deposits"
        ),
        json={
            "reference":
                TEST_REFERENCE,
            "amount":
                "12.50",
            "currency":
                TEST_CURRENCY,
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert (
        data["reference"]
        == TEST_REFERENCE
    )

    assert (
        data["reserve"][
            "verified_balance_micro"
        ]
        == "12500000"
    )


def test_duplicate_deposit_returns_409():
    payload = {
        "reference":
            TEST_REFERENCE,
        "amount":
            "10.00",
        "currency":
            TEST_CURRENCY,
    }

    first = client.post(
        (
            f"{settings.api_prefix}"
            "/treasury/simulated/deposits"
        ),
        json=payload,
    )

    second = client.post(
        (
            f"{settings.api_prefix}"
            "/treasury/simulated/deposits"
        ),
        json=payload,
    )

    assert first.status_code == 201
    assert second.status_code == 409


def test_list_movements():
    client.post(
        (
            f"{settings.api_prefix}"
            "/treasury/simulated/deposits"
        ),
        json={
            "reference":
                TEST_REFERENCE,
            "amount":
                "5.00",
            "currency":
                TEST_CURRENCY,
        },
    )

    response = client.get(
        (
            f"{settings.api_prefix}"
            "/treasury/movements"
        ),
        params={
            "currency":
                TEST_CURRENCY,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["count"] == 1

    assert (
        data["items"][0][
            "reference"
        ]
        == TEST_REFERENCE
    )
