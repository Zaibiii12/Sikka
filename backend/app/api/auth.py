from fastapi import (
    APIRouter,
    Depends,
)

from app.core.auth import (
    Principal,
    get_auth_settings,
    get_current_principal,
    role_policy_catalog,
)


router = APIRouter(
    prefix="/auth",
    tags=["auth"],
)


@router.get("/whoami")
def whoami(
    principal: Principal = Depends(
        get_current_principal
    ),
) -> dict:
    return {
        "subject":
            principal.subject,
        "role":
            principal.role.value,
        "auth_disabled":
            principal.auth_disabled,
    }


@router.get("/policy")
def policy() -> dict:
    settings = get_auth_settings()

    return {
        "auth_required":
            settings.required,
        "policies":
            role_policy_catalog(),
    }
