import os

from fastapi import FastAPI, Request
from starlette.responses import JSONResponse

from app.core.config import get_settings


WRITE_METHODS = frozenset(
    {
        "POST",
        "PUT",
        "PATCH",
        "DELETE",
    }
)

TRUTHY_VALUES = frozenset(
    {
        "1",
        "true",
        "yes",
        "on",
    }
)


def public_read_only_enabled() -> bool:
    value = os.getenv(
        "BLOCKSIKKA_PUBLIC_READ_ONLY",
        "",
    )

    return (
        value
        .strip()
        .lower()
        in TRUTHY_VALUES
    )


def install_public_read_only_middleware(
    app: FastAPI,
) -> None:
    @app.middleware("http")
    async def public_read_only_middleware(
        request: Request,
        call_next,
    ):
        prefix = (
            get_settings()
            .api_prefix
            .rstrip("/")
        )

        path = request.url.path
        method = request.method.upper()

        is_api_path = (
            path == prefix
            or path.startswith(
                f"{prefix}/"
            )
        )

        if (
            public_read_only_enabled()
            and is_api_path
            and method in WRITE_METHODS
        ):
            return JSONResponse(
                status_code=403,
                content={
                    "detail": (
                        "This deployment is "
                        "read-only."
                    )
                },
            )

        return await call_next(
            request
        )
