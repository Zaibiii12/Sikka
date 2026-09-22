import pytest

from fastapi.testclient import (
    TestClient,
)
from sqlalchemy import delete

from app.core.auth import (
    get_auth_settings,
)
from app.core.config import (
    get_settings,
)
from app.db.bank_models import (
    BankAccountRecord,
    BankTransactionRecord,
)
from app.db.session import (
    SessionLocal,
)
from app.main import app


settings = get_settings()
client = TestClient(app)


VIEWER_TOKEN = (
    "test-viewer-token-"
    "000000000000000000000000"
)

PAYMENT_TOKEN = (
    "test-payment-token-"
    "00000000000000000000000"
)

BANK_TOKEN = (
    "test-bank-token-"
    "0000000000000000000000000"
)

TREASURY_TOKEN = (
    "test-treasury-token-"
    "000000000000000000000"
)

ADMIN_TOKEN = (
    "test-admin-token-"
    "000000000000000000000000"
)


BANK_ACCOUNT_ID = (
    "AUTH-RBAC-BANK"
)

ADMIN_ACCOUNT_ID = (
    "AUTH-RBAC-ADMIN-BANK"
)


def _headers(
    token: str,
) -> dict[str, str]:
    return {
        "Authorization":
            f"Bearer {token}",
    }


def _cleanup():
    with SessionLocal() as db:
        db.execute(
            delete(
                BankTransactionRecord
            )
            .where(
                BankTransactionRecord
                .account_id
                .in_(
                    [
                        BANK_ACCOUNT_ID,
                        ADMIN_ACCOUNT_ID,
                    ]
                )
            )
        )

        db.execute(
            delete(BankAccountRecord)
            .where(
                BankAccountRecord
                .account_id
                .in_(
                    [
                        BANK_ACCOUNT_ID,
                        ADMIN_ACCOUNT_ID,
                    ]
                )
            )
        )

        db.commit()


@pytest.fixture(autouse=True)
def auth_enabled(
    monkeypatch,
):
    _cleanup()

    monkeypatch.setenv(
        "BLOCKSIKKA_AUTH_REQUIRED",
        "true",
    )

    monkeypatch.setenv(
        "BLOCKSIKKA_AUTH_VIEWER_TOKEN",
        VIEWER_TOKEN,
    )

    monkeypatch.setenv(
        (
            "BLOCKSIKKA_AUTH_"
            "PAYMENT_OPERATOR_TOKEN"
        ),
        PAYMENT_TOKEN,
    )

    monkeypatch.setenv(
        (
            "BLOCKSIKKA_AUTH_"
            "BANK_OPERATOR_TOKEN"
        ),
        BANK_TOKEN,
    )

    monkeypatch.setenv(
        (
            "BLOCKSIKKA_AUTH_"
            "TREASURY_OPERATOR_TOKEN"
        ),
        TREASURY_TOKEN,
    )

    monkeypatch.setenv(
        (
            "BLOCKSIKKA_AUTH_"
            "TREASURY_ADMIN_TOKEN"
        ),
        ADMIN_TOKEN,
    )

    get_auth_settings.cache_clear()

    yield

    get_auth_settings.cache_clear()

    _cleanup()


def test_public_read_remains_available():
    response = client.get("/")

    assert response.status_code == 200


def test_missing_credentials_returns_401():
    response = client.post(
        (
            f"{settings.api_prefix}"
            "/mock-bank/accounts"
        ),
        json={
            "account_id":
                BANK_ACCOUNT_ID,
            "name":
                "Auth Bank",
            "currency":
                "AUT",
        },
    )

    assert response.status_code == 401

    assert (
        response.headers[
            "www-authenticate"
        ]
        == "Bearer"
    )


def test_invalid_credentials_returns_401():
    response = client.post(
        (
            f"{settings.api_prefix}"
            "/mock-bank/accounts"
        ),
        headers=_headers(
            "definitely-invalid-token"
        ),
        json={
            "account_id":
                BANK_ACCOUNT_ID,
            "name":
                "Auth Bank",
            "currency":
                "AUT",
        },
    )

    assert response.status_code == 401


def test_wrong_role_returns_403():
    response = client.post(
        (
            f"{settings.api_prefix}"
            "/mock-bank/accounts"
        ),
        headers=_headers(
            PAYMENT_TOKEN
        ),
        json={
            "account_id":
                BANK_ACCOUNT_ID,
            "name":
                "Auth Bank",
            "currency":
                "AUT",
        },
    )

    assert response.status_code == 403


def test_bank_operator_can_write_mock_bank():
    response = client.post(
        (
            f"{settings.api_prefix}"
            "/mock-bank/accounts"
        ),
        headers=_headers(
            BANK_TOKEN
        ),
        json={
            "account_id":
                BANK_ACCOUNT_ID,
            "name":
                "Authorized Bank",
            "currency":
                "AUT",
        },
    )

    assert response.status_code == 201


def test_treasury_operator_reaches_ingestion_logic():
    response = client.post(
        (
            f"{settings.api_prefix}"
            "/treasury/"
            "bank-settlements/"
            "AUTH-NOT-FOUND/ingest"
        ),
        headers=_headers(
            TREASURY_TOKEN
        ),
        json={
            "currency":
                "USD",
        },
    )

    #
    # 404 proves authorization passed and
    # business logic handled the request.
    #
    assert response.status_code == 404


def test_bank_operator_cannot_mint():
    response = client.post(
        (
            f"{settings.api_prefix}"
            "/treasury/mint"
        ),
        headers=_headers(
            BANK_TOKEN
        ),
        json={
            "reference":
                "AUTH-DENIED-MINT-001",
            "bank_address":
                (
                    "0x1EC30b4058188c2c14e"
                    "A5AB2930d71911F38f6cB"
                ),
            "amount":
                "1.000000",
            "currency":
                "USD",
        },
    )

    assert response.status_code == 403


def test_admin_inherits_bank_write_access():
    response = client.post(
        (
            f"{settings.api_prefix}"
            "/mock-bank/accounts"
        ),
        headers=_headers(
            ADMIN_TOKEN
        ),
        json={
            "account_id":
                ADMIN_ACCOUNT_ID,
            "name":
                "Administrator Bank",
            "currency":
                "AUT",
        },
    )

    assert response.status_code == 201


def test_whoami_returns_identity_not_token():
    response = client.get(
        (
            f"{settings.api_prefix}"
            "/auth/whoami"
        ),
        headers=_headers(
            BANK_TOKEN
        ),
    )

    assert response.status_code == 200

    data = response.json()

    assert (
        data["subject"]
        == "bank-operator"
    )

    assert (
        data["role"]
        == "BANK_OPERATOR"
    )

    serialized = str(data)

    assert BANK_TOKEN not in serialized
