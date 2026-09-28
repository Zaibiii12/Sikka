import os

from sqlalchemy.engine import make_url


# ------------------------------------------------------------
# DEFAULT TEST AUTH MODE
# ------------------------------------------------------------
#
# Force authentication OFF for normal regression tests.
#
# Dedicated auth/RBAC tests explicitly enable authentication
# themselves when they need to test protected behavior.
#
# Do not use setdefault() here because the developer shell may
# already contain BLOCKSIKKA_AUTH_REQUIRED=true after .env was
# sourced manually.
# ------------------------------------------------------------

os.environ["BLOCKSIKKA_AUTH_REQUIRED"] = "false"


# ------------------------------------------------------------
# DATABASE SAFETY GUARD
# ------------------------------------------------------------
#
# Pytest must NEVER run against the normal development database.
# ------------------------------------------------------------

from app.core.config import get_settings  # noqa: E402


database_url = make_url(
    get_settings().database_url
)

database_name = database_url.database


if database_name != "blocksikka_test":
    raise RuntimeError(
        "\n"
        "BLOCKSIKKA TEST SAFETY GUARD\n"
        "---------------------------\n"
        "Pytest refused to start because DATABASE_URL points to:\n"
        f"    {database_name!r}\n\n"
        "Tests are only allowed to use:\n"
        "    blocksikka_test\n\n"
        "Run tests through:\n"
        "    ./scripts/test_safe.sh\n"
    )
