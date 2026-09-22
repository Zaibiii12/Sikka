from app.banking.faults import (
    BankFaultMode,
)


def bank_failure_simulation_catalog(
) -> list[dict]:
    return [
        {
            "mode":
                BankFaultMode.UNAVAILABLE,
            "category":
                "availability",
            "description":
                (
                    "External bank provider "
                    "cannot be reached."
                ),
            "expected_control":
                "fail_closed",
        },
        {
            "mode":
                BankFaultMode.STALE_STATUS,
            "category":
                "stale_data",
            "description":
                (
                    "Provider returns a stale "
                    "PENDING transaction state."
                ),
            "expected_control":
                "reject_nonfinal",
        },
        {
            "mode":
                BankFaultMode.WRONG_CURRENCY,
            "category":
                "data_integrity",
            "description":
                (
                    "Provider returns a "
                    "different currency."
                ),
            "expected_control":
                "reject",
        },
        {
            "mode":
                BankFaultMode.WRONG_DIRECTION,
            "category":
                "data_integrity",
            "description":
                (
                    "Provider reports CREDIT "
                    "as DEBIT."
                ),
            "expected_control":
                "reject",
        },
        {
            "mode":
                BankFaultMode.NEGATIVE_AMOUNT,
            "category":
                "malformed_data",
            "description":
                (
                    "Provider returns an "
                    "invalid negative amount."
                ),
            "expected_control":
                "reject",
        },
        {
            "mode":
                BankFaultMode.OMIT_LIST,
            "category":
                "reconciliation",
            "description":
                (
                    "Provider omits real "
                    "transactions from listing."
                ),
            "expected_control":
                (
                    "detect_during_"
                    "reconciliation"
                ),
        },
        {
            "mode":
                BankFaultMode.DUPLICATE_LIST,
            "category":
                "reconciliation",
            "description":
                (
                    "Provider duplicates a "
                    "transaction in listing."
                ),
            "expected_control":
                "deduplicate_or_flag",
        },
    ]
