import argparse

from app.db.session import SessionLocal
from app.services.treasury import (
    DuplicateReferenceError,
    TreasuryError,
    format_micro_units,
    parse_amount_to_micro_units,
    record_verified_deposit,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Record a simulated verified USD reserve deposit."
        )
    )

    parser.add_argument(
        "--reference",
        required=True,
        help="Unique fiat deposit reference.",
    )

    parser.add_argument(
        "--amount",
        required=True,
        help=(
            "USD amount, for example 100000.00"
        ),
    )

    parser.add_argument(
        "--bank-address",
        default=None,
        help=(
            "Optional associated BlockSikka bank address."
        ),
    )

    args = parser.parse_args()

    try:
        amount_micro = (
            parse_amount_to_micro_units(
                args.amount
            )
        )

        with SessionLocal() as db:
            movement, reserve = (
                record_verified_deposit(
                    db,
                    reference=args.reference,
                    amount_micro=
                        amount_micro,
                    currency="USD",
                    bank_address=
                        args.bank_address,
                    external_reference=
                        args.reference,
                    details={
                        "source":
                            "SIMULATED_BANK",
                    },
                )
            )

            db.commit()

            print(
                "Verified simulated USD deposit recorded"
            )
            print(
                f"movement_id={movement.id}"
            )
            print(
                f"reference={movement.reference}"
            )
            print(
                "deposit="
                + format_micro_units(
                    movement.amount
                )
                + " USD"
            )
            print(
                "verified_reserve="
                + format_micro_units(
                    reserve.verified_balance
                )
                + " USD"
            )

    except (
        TreasuryError,
        DuplicateReferenceError,
    ) as exc:
        raise SystemExit(
            f"ERROR: {exc}"
        ) from exc


if __name__ == "__main__":
    main()
