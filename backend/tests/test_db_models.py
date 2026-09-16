from app.db import models  # noqa: F401
from app.db.base import Base


def test_phase10_database_tables_registered() -> None:
    tables = set(
        Base.metadata.tables.keys()
    )

    expected = {
        "indexer_state",
        "chain_events",
        "payments",
        "settlements",
        "settlement_payments",
        "banks",
        "token_transfers",
    }

    assert expected.issubset(tables)
