from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.treasury import (
    SimulatedDepositRequest,
    TreasuryMintRequest,
    TreasuryRedemptionRequest,
)
from app.services.treasury import (
    DuplicateReferenceError,
    ReserveNotFoundError,
    TreasuryError,
    list_fiat_movements,
    parse_amount_to_micro_units,
    record_verified_deposit,
    reserve_summary,
    onchain_reserve_summary,
)


from app.services.bank_reversal import UnresolvedBankReversalError
from app.services.treasury_mint import (
    BankNotEligibleError,
    DuplicateMintRequestError,
    InsufficientReserveCapacityError,
    MintExecutionError,
    MintWorkflowError,
    ReserveOutOfSyncError,
    execute_reserve_backed_mint,
    get_mint_request,
    list_mint_requests,
    serialize_mint_request,
)



from app.services.treasury_redemption import (
    DuplicateRedemptionError,
    InsufficientFiatReserveError,
    InsufficientSikkaBalanceError,
    RedemptionBankError,
    RedemptionExecutionError,
    RedemptionPostBurnError,
    RedemptionReserveOutOfSyncError,
    RedemptionWorkflowError,
    execute_redemption,
    get_redemption,
    list_redemptions,
    serialize_redemption,
)



from app.services.treasury_reconciliation import (
    ReconciliationError,
    current_reconciliation,
    list_reconciliations,
    record_reconciliation,
    serialize_reconciliation,
    treasury_exceptions,
)



from app.services.treasury_recovery import (
    RecoveryError,
    recovery_status,
    run_recovery,
)



router = APIRouter(
    prefix="/treasury",
    tags=["treasury"],
)


@router.get("/reserve")
def reserve(
    currency: str = Query(
        "USD",
        min_length=3,
        max_length=3,
    ),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return reserve_summary(
            db,
            currency=currency,
        )

    except ReserveNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc


@router.get("/onchain")
def onchain() -> dict:
    try:
        return onchain_reserve_summary()

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc


@router.get("/movements")
def movements(
    currency: str = Query(
        "USD",
        min_length=3,
        max_length=3,
    ),
    limit: int = Query(
        100,
        ge=1,
        le=500,
    ),
    offset: int = Query(
        0,
        ge=0,
    ),
    db: Session = Depends(get_db),
) -> dict:
    rows = list_fiat_movements(
        db,
        currency=currency,
        limit=limit,
        offset=offset,
    )

    return {
        "count": len(rows),
        "limit": limit,
        "offset": offset,
        "items": rows,
    }


@router.post(
    "/simulated/deposits",
    status_code=201,
)
def simulated_deposit(
    request: SimulatedDepositRequest,
    db: Session = Depends(get_db),
) -> dict:
    """
    Development-only simulated bank deposit.

    This represents confirmation from an external
    reserve bank. It does not move real fiat.
    """

    try:
        amount_micro = (
            parse_amount_to_micro_units(
                request.amount
            )
        )

        movement, _ = (
            record_verified_deposit(
                db,
                reference=
                    request.reference,
                amount_micro=
                    amount_micro,
                currency=
                    request.currency,
                bank_address=
                    request.bank_address,
                external_reference=(
                    request.external_reference
                    or request.reference
                ),
                details={
                    "source":
                        "SIMULATED_BANK_API",
                },
            )
        )

        db.commit()

        return {
            "movement_id":
                movement.id,
            "reference":
                movement.reference,
            "reserve":
                reserve_summary(
                    db,
                    currency=
                        request.currency,
                ),
        }

    except DuplicateReferenceError as exc:
        db.rollback()

        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    except ReserveNotFoundError as exc:
        db.rollback()

        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except TreasuryError as exc:
        db.rollback()

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except IntegrityError as exc:
        db.rollback()

        raise HTTPException(
            status_code=409,
            detail=(
                "Fiat movement could not be "
                "created because its reference "
                "already exists."
            ),
        ) from exc


@router.post(
    "/mint",
    status_code=201,
)
def mint(
    request: TreasuryMintRequest,
    db: Session = Depends(get_db),
) -> dict:
    try:
        amount_micro = (
            parse_amount_to_micro_units(
                request.amount
            )
        )

        row = execute_reserve_backed_mint(
            db,
            reference=request.reference,
            bank_address=
                request.bank_address,
            amount_micro=amount_micro,
            currency=request.currency,
        )

        return serialize_mint_request(
            row
        )


    except UnresolvedBankReversalError as exc:
        db.rollback()

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except DuplicateMintRequestError as exc:
        db.rollback()

        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    except (
        ReserveOutOfSyncError,
        InsufficientReserveCapacityError,
    ) as exc:
        db.rollback()

        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    except BankNotEligibleError as exc:
        db.rollback()

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except MintExecutionError as exc:
        db.rollback()

        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc

    except MintWorkflowError as exc:
        db.rollback()

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.get("/mint-requests")
def mint_requests(
    limit: int = Query(
        100,
        ge=1,
        le=500,
    ),
    offset: int = Query(
        0,
        ge=0,
    ),
    db: Session = Depends(get_db),
) -> dict:
    rows = list_mint_requests(
        db,
        limit=limit,
        offset=offset,
    )

    return {
        "count": len(rows),
        "limit": limit,
        "offset": offset,
        "items": [
            serialize_mint_request(
                row
            )
            for row in rows
        ],
    }


@router.get(
    "/mint-requests/{request_id}"
)
def mint_request(
    request_id: str,
    db: Session = Depends(get_db),
) -> dict:
    row = get_mint_request(
        db,
        request_id=request_id,
    )

    if row is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Mint request not found."
            ),
        )

    return serialize_mint_request(
        row
    )


@router.post(
    "/redeem",
    status_code=201,
)
def redeem(
    request: TreasuryRedemptionRequest,
    db: Session = Depends(get_db),
) -> dict:
    try:
        amount_micro = (
            parse_amount_to_micro_units(
                request.amount
            )
        )

        row = execute_redemption(
            db,
            reference=request.reference,
            bank_address=
                request.bank_address,
            amount_micro=amount_micro,
            currency=request.currency,
        )

        return serialize_redemption(
            row
        )

    except DuplicateRedemptionError as exc:
        db.rollback()

        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    except (
        InsufficientFiatReserveError,
        InsufficientSikkaBalanceError,
        RedemptionReserveOutOfSyncError,
    ) as exc:
        db.rollback()

        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    except RedemptionBankError as exc:
        db.rollback()

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except RedemptionPostBurnError as exc:
        db.rollback()

        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc

    except RedemptionExecutionError as exc:
        db.rollback()

        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc

    except RedemptionWorkflowError as exc:
        db.rollback()

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.get("/redemptions")
def redemptions(
    limit: int = Query(
        100,
        ge=1,
        le=500,
    ),
    offset: int = Query(
        0,
        ge=0,
    ),
    db: Session = Depends(get_db),
) -> dict:
    rows = list_redemptions(
        db,
        limit=limit,
        offset=offset,
    )

    return {
        "count": len(rows),
        "limit": limit,
        "offset": offset,
        "items": [
            serialize_redemption(
                row
            )
            for row in rows
        ],
    }


@router.get(
    "/redemptions/{request_id}"
)
def redemption(
    request_id: str,
    db: Session = Depends(get_db),
) -> dict:
    row = get_redemption(
        db,
        request_id=request_id,
    )

    if row is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Redemption request "
                "not found."
            ),
        )

    return serialize_redemption(
        row
    )


@router.get("/reconciliation")
def reconciliation(
    currency: str = Query(
        "USD",
        min_length=3,
        max_length=3,
    ),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return current_reconciliation(
            db,
            currency=currency,
        )

    except ReconciliationError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.post("/reconcile")
def reconcile(
    currency: str = Query(
        "USD",
        min_length=3,
        max_length=3,
    ),
    db: Session = Depends(get_db),
) -> dict:
    try:
        row = record_reconciliation(
            db,
            currency=currency,
        )

        return serialize_reconciliation(
            row
        )

    except ReconciliationError as exc:
        db.rollback()

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.get(
    "/reconciliation/history"
)
def reconciliation_history(
    limit: int = Query(
        100,
        ge=1,
        le=500,
    ),
    offset: int = Query(
        0,
        ge=0,
    ),
    db: Session = Depends(get_db),
) -> dict:
    rows = list_reconciliations(
        db,
        limit=limit,
        offset=offset,
    )

    return {
        "count": len(rows),
        "limit": limit,
        "offset": offset,
        "items": [
            serialize_reconciliation(
                row
            )
            for row in rows
        ],
    }


@router.get("/exceptions")
def exceptions(
    currency: str = Query(
        "USD",
        min_length=3,
        max_length=3,
    ),
    stale_minutes: int = Query(
        5,
        ge=1,
        le=1440,
    ),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return treasury_exceptions(
            db,
            currency=currency,
            stale_minutes=
                stale_minutes,
        )

    except ReconciliationError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.get("/recovery/status")
def treasury_recovery_status(
    db: Session = Depends(get_db),
) -> dict:
    return recovery_status(db)


@router.post("/recovery/run")
def treasury_recovery_run(
    limit: int = Query(
        100,
        ge=1,
        le=500,
    ),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return run_recovery(
            db,
            limit=limit,
        )

    except RecoveryError as exc:
        db.rollback()

        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc
