import pytest
from fastapi import HTTPException

from app.core.auth import (
    AuthRole,
    authenticate_authorization,
    get_auth_settings,
    required_roles_for_request,
)
from app.core.config import get_settings


VIEWER_TOKEN = "edge-viewer-token"
PAYMENT_TOKEN = "edge-payment-token"
BANK_TOKEN = "edge-bank-token"
TREASURY_TOKEN = "edge-treasury-token"
ADMIN_TOKEN = "edge-admin-token"


def configure_auth(
    monkeypatch,
    *,
    required: bool = True,
    viewer: str = VIEWER_TOKEN,
    payment: str = PAYMENT_TOKEN,
    bank: str = BANK_TOKEN,
    treasury: str = TREASURY_TOKEN,
    admin: str = ADMIN_TOKEN,
):
    """
    Configure every auth environment variable explicitly.

    Setting every token here makes these tests deterministic even if
    backend/.env contains development tokens.
    """
    monkeypatch.setenv(
        "BLOCKSIKKA_AUTH_REQUIRED",
        "true" if required else "false",
    )

    monkeypatch.setenv(
        "BLOCKSIKKA_AUTH_VIEWER_TOKEN",
        viewer,
    )

    monkeypatch.setenv(
        "BLOCKSIKKA_AUTH_PAYMENT_OPERATOR_TOKEN",
        payment,
    )

    monkeypatch.setenv(
        "BLOCKSIKKA_AUTH_BANK_OPERATOR_TOKEN",
        bank,
    )

    monkeypatch.setenv(
        "BLOCKSIKKA_AUTH_TREASURY_OPERATOR_TOKEN",
        treasury,
    )

    monkeypatch.setenv(
        "BLOCKSIKKA_AUTH_TREASURY_ADMIN_TOKEN",
        admin,
    )

    # Auth settings are cached, so force a reload after changing env.
    get_auth_settings.cache_clear()


@pytest.fixture
def auth_enabled(monkeypatch):
    configure_auth(monkeypatch)

    yield

    # Never let cached test configuration leak into another test.
    get_auth_settings.cache_clear()


def test_wrong_authorization_scheme_returns_401(
    auth_enabled,
):
    with pytest.raises(HTTPException) as exc:
        authenticate_authorization(
            "Basic definitely-not-valid"
        )

    assert exc.value.status_code == 401
    assert (
        exc.value.headers["WWW-Authenticate"]
        == "Bearer"
    )


def test_blank_bearer_token_returns_401(
    auth_enabled,
):
    with pytest.raises(HTTPException) as exc:
        authenticate_authorization(
            "Bearer    "
        )

    assert exc.value.status_code == 401


@pytest.mark.parametrize(
    ("token", "expected_role"),
    [
        (
            VIEWER_TOKEN,
            AuthRole.VIEWER,
        ),
        (
            PAYMENT_TOKEN,
            AuthRole.PAYMENT_OPERATOR,
        ),
        (
            BANK_TOKEN,
            AuthRole.BANK_OPERATOR,
        ),
        (
            TREASURY_TOKEN,
            AuthRole.TREASURY_OPERATOR,
        ),
        (
            ADMIN_TOKEN,
            AuthRole.TREASURY_ADMIN,
        ),
    ],
)
def test_each_configured_token_maps_to_correct_role(
    auth_enabled,
    token,
    expected_role,
):
    principal = authenticate_authorization(
        f"Bearer {token}"
    )

    assert principal.role == expected_role
    assert principal.auth_disabled is False


def test_duplicate_tokens_fail_configuration(
    monkeypatch,
):
    configure_auth(
        monkeypatch,
        viewer="duplicate-secret",
        payment="duplicate-secret",
    )

    with pytest.raises(
        RuntimeError,
        match="Duplicate authentication tokens",
    ):
        authenticate_authorization(
            "Bearer duplicate-secret"
        )

    get_auth_settings.cache_clear()


def test_auth_disabled_returns_explicit_admin_principal(
    monkeypatch,
):
    configure_auth(
        monkeypatch,
        required=False,
    )

    principal = authenticate_authorization(None)

    assert principal.subject == "auth-disabled"
    assert principal.role == AuthRole.TREASURY_ADMIN
    assert principal.auth_disabled is True

    get_auth_settings.cache_clear()


@pytest.mark.parametrize(
    "method",
    [
        "GET",
        "HEAD",
        "OPTIONS",
    ],
)
def test_read_requests_do_not_require_write_role(
    method,
):
    prefix = (
        get_settings()
        .api_prefix
        .rstrip("/")
    )

    required = required_roles_for_request(
        method,
        f"{prefix}/treasury/mint",
    )

    assert required is None


@pytest.mark.parametrize(
    ("relative_path", "expected_roles"),
    [
        (
            "/mock-bank/test",
            {
                AuthRole.BANK_OPERATOR,
                AuthRole.TREASURY_ADMIN,
            },
        ),
        (
            "/banks/admin/test",
            {
                AuthRole.BANK_OPERATOR,
                AuthRole.TREASURY_ADMIN,
            },
        ),
        (
            "/treasury/bank-settlements/test",
            {
                AuthRole.TREASURY_OPERATOR,
                AuthRole.TREASURY_ADMIN,
            },
        ),
        (
            "/treasury/bank-reversals/test",
            {
                AuthRole.TREASURY_OPERATOR,
                AuthRole.TREASURY_ADMIN,
            },
        ),
        (
            "/treasury/bank-reversals/test/resolve",
            {
                AuthRole.TREASURY_ADMIN,
            },
        ),
        (
            "/treasury/simulated/deposits",
            {
                AuthRole.TREASURY_OPERATOR,
                AuthRole.TREASURY_ADMIN,
            },
        ),
        (
            "/treasury/mint",
            {
                AuthRole.TREASURY_ADMIN,
            },
        ),
        (
            "/treasury/redeem",
            {
                AuthRole.TREASURY_ADMIN,
            },
        ),
        (
            "/treasury/reconcile",
            {
                AuthRole.TREASURY_ADMIN,
            },
        ),
        (
            "/treasury/recovery/run",
            {
                AuthRole.TREASURY_ADMIN,
            },
        ),
        (
            "/token/admin/test",
            {
                AuthRole.TREASURY_ADMIN,
            },
        ),
        (
            "/payments/prepare",
            {
                AuthRole.PAYMENT_OPERATOR,
                AuthRole.TREASURY_ADMIN,
            },
        ),
        (
            "/payments/relay",
            {
                AuthRole.PAYMENT_OPERATOR,
                AuthRole.TREASURY_ADMIN,
            },
        ),
        (
            "/settlements",
            {
                AuthRole.PAYMENT_OPERATOR,
                AuthRole.TREASURY_ADMIN,
            },
        ),
        (
            "/settlements/example",
            {
                AuthRole.PAYMENT_OPERATOR,
                AuthRole.TREASURY_ADMIN,
            },
        ),
    ],
)
def test_write_policy_matrix(
    relative_path,
    expected_roles,
):
    prefix = (
        get_settings()
        .api_prefix
        .rstrip("/")
    )

    required = required_roles_for_request(
        "POST",
        f"{prefix}{relative_path}",
    )

    assert required == expected_roles


@pytest.mark.parametrize(
    "method",
    [
        "POST",
        "PUT",
        "PATCH",
        "DELETE",
    ],
)
def test_unknown_api_write_route_fails_closed(
    method,
):
    """
    New write endpoints must not silently become public.

    Unless a narrower policy is explicitly added,
    TREASURY_ADMIN is required.
    """
    prefix = (
        get_settings()
        .api_prefix
        .rstrip("/")
    )

    required = required_roles_for_request(
        method,
        f"{prefix}/future/new-write-route",
    )

    assert required == {
        AuthRole.TREASURY_ADMIN
    }


def test_write_outside_api_prefix_is_not_intercepted():
    required = required_roles_for_request(
        "POST",
        "/some-non-api-route",
    )

    assert required is None
