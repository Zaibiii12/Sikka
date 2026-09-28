#!/usr/bin/env bash
set -euo pipefail

BACKEND_ROOT="$(
    cd "$(dirname "$0")/.." &&
    pwd
)"

cd "$BACKEND_ROOT"

PYTHON="$BACKEND_ROOT/.venv/bin/python"
PYTEST="$BACKEND_ROOT/.venv/bin/pytest"
ALEMBIC="$BACKEND_ROOT/.venv/bin/alembic"

POSTGRES_CONTAINER="${BLOCKSIKKA_POSTGRES_CONTAINER:-blocksikka-postgres}"
TEST_DATABASE_NAME="blocksikka_test"


echo "======================================"
echo " BlockSikka safe test environment"
echo "======================================"
echo


if ! docker inspect "$POSTGRES_CONTAINER" >/dev/null 2>&1; then
    echo "ERROR: PostgreSQL container not found:"
    echo "  $POSTGRES_CONTAINER"
    exit 1
fi


echo "[1/5] Recreating isolated test database..."

docker exec "$POSTGRES_CONTAINER" sh -lc '
    set -eu

    dropdb \
        --if-exists \
        --force \
        -U "$POSTGRES_USER" \
        blocksikka_test

    createdb \
        -U "$POSTGRES_USER" \
        blocksikka_test
'

echo "Fresh blocksikka_test created."


echo
echo "[2/5] Building isolated test DATABASE_URL..."

LIVE_DATABASE_URL="$(
    "$PYTHON" - <<'PY'
from app.core.config import get_settings

print(
    get_settings().database_url
)
PY
)"

TEST_DATABASE_URL="$(
    LIVE_DATABASE_URL="$LIVE_DATABASE_URL" \
    "$PYTHON" - <<'PY'
import os

from sqlalchemy.engine import make_url


url = make_url(
    os.environ["LIVE_DATABASE_URL"]
)

test_url = url.set(
    database="blocksikka_test"
)

print(
    test_url.render_as_string(
        hide_password=False
    )
)
PY
)"

export DATABASE_URL="$TEST_DATABASE_URL"

unset LIVE_DATABASE_URL
unset TEST_DATABASE_URL

# Normal regression suite runs with API authentication disabled.
export BLOCKSIKKA_AUTH_REQUIRED="false"

echo "Test database: blocksikka_test"
echo "Test authentication: disabled"


echo
echo "[3/5] Applying database migrations..."

"$ALEMBIC" upgrade head

echo "Database schema ready."


echo
echo "[4/5] Initializing and synchronizing test reserve..."

"$PYTHON" -m scripts.treasury_init

CHAIN_RESERVE_MICRO="$(
    "$PYTHON" - <<'PY'
from app.core.contracts import get_contracts


contracts = get_contracts()

reserve = int(
    contracts
    .reserve_controller
    .functions
    .verifiedReserve()
    .call()
)

print(reserve)
PY
)"

CHAIN_RESERVE_MICRO="$CHAIN_RESERVE_MICRO" \
"$PYTHON" - <<'PY'
import os
from decimal import Decimal

from app.db.models import ReserveAccount
from app.db.session import SessionLocal


reserve_micro = int(
    os.environ["CHAIN_RESERVE_MICRO"]
)

with SessionLocal() as db:
    account = db.get(
        ReserveAccount,
        "USD",
    )

    if account is None:
        raise SystemExit(
            "ERROR: USD reserve account was not initialized."
        )

    # Test bootstrap state only.
    #
    # Do not create a FiatMovement here because API tests need to
    # control their own movement history.
    account.verified_balance = Decimal(
        reserve_micro
    )

    account.reserved_balance = Decimal(0)

    account.version += 1

    db.commit()

print(
    "Test reserve synchronized to on-chain value:"
    f" {reserve_micro} micro-USD"
)
PY


echo
echo "[5/5] Running tests..."
echo

if [ "$#" -gt 0 ]; then
    exec "$PYTEST" "$@"
fi


# Real-network E2E tests remain separate because they submit actual
# transactions to the running Besu development chain.
exec "$PYTEST" \
    -q \
    --ignore=tests/test_real_network_payment_e2e.py \
    --ignore=tests/test_real_network_settlement_e2e.py
