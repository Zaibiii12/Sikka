from app.db.session import SessionLocal
from app.services.treasury import (
    format_micro_units,
    initialize_reserve_account,
)


def main() -> None:
    with SessionLocal() as db:
        account = initialize_reserve_account(
            db,
            currency="USD",
            source_type="SIMULATED",
        )

        db.commit()
        db.refresh(account)

        print("Treasury reserve initialized")
        print(f"currency={account.currency}")
        print(f"source={account.source_type}")
        print(
            "verified="
            + format_micro_units(
                account.verified_balance
            )
        )
        print(
            "reserved="
            + format_micro_units(
                account.reserved_balance
            )
        )


if __name__ == "__main__":
    main()
