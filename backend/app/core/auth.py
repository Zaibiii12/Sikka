import logging
import secrets

from dataclasses import dataclass
from enum import StrEnum
from functools import lru_cache

from fastapi import (
    Header,
    HTTPException,
    Request,
)
from pydantic import SecretStr
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)
from starlette.responses import JSONResponse

from app.core.config import get_settings


security_logger = logging.getLogger(
    "blocksikka.security"
)


class AuthRole(StrEnum):
    VIEWER = "VIEWER"

    PAYMENT_OPERATOR = (
        "PAYMENT_OPERATOR"
    )

    BANK_OPERATOR = (
        "BANK_OPERATOR"
    )

    TREASURY_OPERATOR = (
        "TREASURY_OPERATOR"
    )

    TREASURY_ADMIN = (
        "TREASURY_ADMIN"
    )


@dataclass(
    frozen=True,
    slots=True,
)
class Principal:
    subject: str
    role: AuthRole
    auth_disabled: bool = False


class AuthSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="BLOCKSIKKA_AUTH_",
        extra="ignore",
        case_sensitive=False,
    )

    required: bool = True

    viewer_token: (
        SecretStr | None
    ) = None

    payment_operator_token: (
        SecretStr | None
    ) = None

    bank_operator_token: (
        SecretStr | None
    ) = None

    treasury_operator_token: (
        SecretStr | None
    ) = None

    treasury_admin_token: (
        SecretStr | None
    ) = None


@lru_cache
def get_auth_settings(
) -> AuthSettings:
    return AuthSettings()


def _value(
    secret: SecretStr | None,
) -> str | None:
    if secret is None:
        return None

    value = (
        secret
        .get_secret_value()
        .strip()
    )

    return value or None


def _token_catalog(
    settings: AuthSettings,
) -> list[
    tuple[str, AuthRole, str]
]:
    raw = [
        (
            "viewer",
            AuthRole.VIEWER,
            _value(
                settings.viewer_token
            ),
        ),
        (
            "payment-operator",
            AuthRole.PAYMENT_OPERATOR,
            _value(
                settings
                .payment_operator_token
            ),
        ),
        (
            "bank-operator",
            AuthRole.BANK_OPERATOR,
            _value(
                settings
                .bank_operator_token
            ),
        ),
        (
            "treasury-operator",
            AuthRole.TREASURY_OPERATOR,
            _value(
                settings
                .treasury_operator_token
            ),
        ),
        (
            "treasury-admin",
            AuthRole.TREASURY_ADMIN,
            _value(
                settings
                .treasury_admin_token
            ),
        ),
    ]

    configured = [
        (
            subject,
            role,
            token,
        )
        for (
            subject,
            role,
            token,
        )
        in raw
        if token is not None
    ]

    seen: set[str] = set()

    for _, _, token in configured:
        if token in seen:
            raise RuntimeError(
                "Duplicate authentication "
                "tokens are configured."
            )

        seen.add(token)

    return configured


def _unauthorized(
    detail: str,
) -> HTTPException:
    return HTTPException(
        status_code=401,
        detail=detail,
        headers={
            "WWW-Authenticate":
                "Bearer",
        },
    )


def authenticate_authorization(
    authorization: str | None,
) -> Principal:
    settings = get_auth_settings()

    if not settings.required:
        return Principal(
            subject="auth-disabled",
            role=(
                AuthRole
                .TREASURY_ADMIN
            ),
            auth_disabled=True,
        )

    if not authorization:
        raise _unauthorized(
            "Authentication required."
        )

    parts = authorization.split(
        None,
        1,
    )

    if (
        len(parts) != 2
        or parts[0].lower()
        != "bearer"
    ):
        raise _unauthorized(
            "Invalid authorization scheme."
        )

    candidate = parts[1].strip()

    if not candidate:
        raise _unauthorized(
            "Bearer token is required."
        )

    for (
        subject,
        role,
        configured_token,
    ) in _token_catalog(settings):
        if secrets.compare_digest(
            candidate,
            configured_token,
        ):
            return Principal(
                subject=subject,
                role=role,
            )

    raise _unauthorized(
        "Invalid bearer token."
    )


def get_current_principal(
    request: Request,
    authorization: str | None = Header(
        default=None,
        alias="Authorization",
    ),
) -> Principal:
    principal = (
        authenticate_authorization(
            authorization
        )
    )

    request.state.principal = (
        principal
    )

    return principal


WRITE_METHODS = {
    "POST",
    "PUT",
    "PATCH",
    "DELETE",
}


def required_roles_for_request(
    method: str,
    path: str,
) -> set[AuthRole] | None:
    method = method.upper()

    if method not in WRITE_METHODS:
        return None

    prefix = (
        get_settings()
        .api_prefix
        .rstrip("/")
    )

    if not path.startswith(prefix):
        return None

    relative = (
        path[len(prefix):]
        or "/"
    )

    admin = (
        AuthRole.TREASURY_ADMIN
    )

    if relative.startswith(
        "/mock-bank/"
    ):
        return {
            AuthRole.BANK_OPERATOR,
            admin,
        }

    if relative.startswith(
        "/banks/admin/"
    ):
        return {
            AuthRole.BANK_OPERATOR,
            admin,
        }

    if relative.startswith(
        "/treasury/"
        "bank-settlements/"
    ):
        return {
            AuthRole
            .TREASURY_OPERATOR,
            admin,
        }

    if relative.startswith(
        "/treasury/"
        "bank-reversals/"
    ):
        if relative.endswith(
            "/resolve"
        ):
            return {
                admin,
            }

        return {
            AuthRole
            .TREASURY_OPERATOR,
            admin,
        }

    if (
        relative
        == "/treasury/"
        "simulated/deposits"
    ):
        return {
            AuthRole
            .TREASURY_OPERATOR,
            admin,
        }

    if relative in {
        "/treasury/mint",
        "/treasury/redeem",
        "/treasury/reconcile",
        "/treasury/recovery/run",
    }:
        return {
            admin,
        }

    if relative.startswith(
        "/token/admin/"
    ):
        return {
            admin,
        }

    if relative in {
        "/payments/prepare",
        "/payments/relay",
    }:
        return {
            AuthRole
            .PAYMENT_OPERATOR,
            admin,
        }

    if (
        relative == "/settlements"
        or relative.startswith(
            "/settlements/"
        )
    ):
        return {
            AuthRole
            .PAYMENT_OPERATOR,
            admin,
        }

    #
    # Fail closed for any future API
    # write route that has not yet
    # received a narrower role policy.
    #
    return {
        admin,
    }


def role_policy_catalog(
) -> list[dict]:
    return [
        {
            "scope":
                "mock-bank writes",
            "roles": [
                "BANK_OPERATOR",
                "TREASURY_ADMIN",
            ],
        },
        {
            "scope":
                "bank settlement ingestion",
            "roles": [
                "TREASURY_OPERATOR",
                "TREASURY_ADMIN",
            ],
        },
        {
            "scope":
                "bank reversal processing",
            "roles": [
                "TREASURY_OPERATOR",
                "TREASURY_ADMIN",
            ],
        },
        {
            "scope":
                "bank reversal resolution",
            "roles": [
                "TREASURY_ADMIN",
            ],
        },
        {
            "scope":
                "mint/redeem/reconcile/recovery",
            "roles": [
                "TREASURY_ADMIN",
            ],
        },
        {
            "scope":
                "bank administration",
            "roles": [
                "BANK_OPERATOR",
                "TREASURY_ADMIN",
            ],
        },
        {
            "scope":
                "token administration",
            "roles": [
                "TREASURY_ADMIN",
            ],
        },
        {
            "scope":
                "payments and settlements",
            "roles": [
                "PAYMENT_OPERATOR",
                "TREASURY_ADMIN",
            ],
        },
    ]


def install_auth_middleware(
    app,
) -> None:
    @app.middleware("http")
    async def rbac_middleware(
        request: Request,
        call_next,
    ):
        required_roles = (
            required_roles_for_request(
                request.method,
                request.url.path,
            )
        )

        settings = (
            get_auth_settings()
        )

        if (
            required_roles is None
            or not settings.required
        ):
            return await call_next(
                request
            )

        authorization = (
            request.headers.get(
                "Authorization"
            )
        )

        try:
            principal = (
                authenticate_authorization(
                    authorization
                )
            )

        except HTTPException as exc:
            security_logger.warning(
                "auth_denied "
                "method=%s path=%s "
                "status=%s subject=anonymous",
                request.method,
                request.url.path,
                exc.status_code,
            )

            headers = (
                exc.headers or {}
            )

            return JSONResponse(
                status_code=
                    exc.status_code,
                content={
                    "detail":
                        exc.detail,
                },
                headers=headers,
            )

        request.state.principal = (
            principal
        )

        if (
            principal.role
            not in required_roles
        ):
            security_logger.warning(
                "auth_forbidden "
                "method=%s path=%s "
                "subject=%s role=%s",
                request.method,
                request.url.path,
                principal.subject,
                principal.role.value,
            )

            return JSONResponse(
                status_code=403,
                content={
                    "detail":
                        (
                            "Insufficient "
                            "role."
                        ),
                },
            )

        response = await call_next(
            request
        )

        security_logger.info(
            "auth_write "
            "method=%s path=%s "
            "subject=%s role=%s "
            "status=%s",
            request.method,
            request.url.path,
            principal.subject,
            principal.role.value,
            response.status_code,
        )

        return response
