from sqlalchemy import select

import app.services.treasury_reconciliation as recon
from app.db.models import ReserveAccount
from app.db.session import SessionLocal


def test_matching_reserves_are_clean(
    monkeypatch,
):
    with SessionLocal() as db:
        account = db.scalar(
            select(ReserveAccount)
            .where(
                ReserveAccount.currency
                == "USD"
            )
        )

        verified = int(
            account.verified_balance
        )

        monkeypatch.setattr(
            recon,
            "_onchain_snapshot",
            lambda: {
                "verified_reserve":
                    verified,
                "total_supply":
                    2_001_000_001,
                "available_mint_capacity":
                    verified
                    - 2_001_000_001,
                "reserve_deficit":
                    0,
            },
        )

        result = (
            recon.current_reconciliation(
                db,
                currency="USD",
            )
        )

        assert result[
            "reserve_matches"
        ] is True

        assert result[
            "fully_backed"
        ] is True

        assert result[
            "clean"
        ] is True

        assert result[
            "reserve_difference_micro"
        ] == "0"


def test_reserve_mismatch_is_detected(
    monkeypatch,
):
    with SessionLocal() as db:
        account = db.scalar(
            select(ReserveAccount)
            .where(
                ReserveAccount.currency
                == "USD"
            )
        )

        verified = int(
            account.verified_balance
        )

        monkeypatch.setattr(
            recon,
            "_onchain_snapshot",
            lambda: {
                "verified_reserve":
                    verified - 1,
                "total_supply":
                    2_001_000_001,
                "available_mint_capacity":
                    verified
                    - 1
                    - 2_001_000_001,
                "reserve_deficit":
                    0,
            },
        )

        result = (
            recon.current_reconciliation(
                db,
                currency="USD",
            )
        )

        assert result[
            "reserve_matches"
        ] is False

        assert result[
            "clean"
        ] is False

        assert result[
            "reserve_difference_micro"
        ] == "-1"


def test_underbacking_is_detected(
    monkeypatch,
):
    with SessionLocal() as db:
        account = db.scalar(
            select(ReserveAccount)
            .where(
                ReserveAccount.currency
                == "USD"
            )
        )

        verified = int(
            account.verified_balance
        )

        monkeypatch.setattr(
            recon,
            "_onchain_snapshot",
            lambda: {
                "verified_reserve":
                    verified,
                "total_supply":
                    verified + 1,
                "available_mint_capacity":
                    0,
                "reserve_deficit":
                    1,
            },
        )

        result = (
            recon.current_reconciliation(
                db,
                currency="USD",
            )
        )

        assert result[
            "fully_backed"
        ] is False

        assert result[
            "clean"
        ] is False


def test_clean_exception_report(
    monkeypatch,
):
    with SessionLocal() as db:
        account = db.scalar(
            select(ReserveAccount)
            .where(
                ReserveAccount.currency
                == "USD"
            )
        )

        verified = int(
            account.verified_balance
        )

        monkeypatch.setattr(
            recon,
            "_onchain_snapshot",
            lambda: {
                "verified_reserve":
                    verified,
                "total_supply":
                    2_001_000_001,
                "available_mint_capacity":
                    verified
                    - 2_001_000_001,
                "reserve_deficit":
                    0,
            },
        )

        result = (
            recon.treasury_exceptions(
                db,
                currency="USD",
                stale_minutes=5,
            )
        )

        assert result[
            "exception_count"
        ] == 0

        assert result[
            "clean"
        ] is True
