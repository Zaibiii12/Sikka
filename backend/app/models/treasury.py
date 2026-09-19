from pydantic import BaseModel, Field


class SimulatedDepositRequest(BaseModel):
    reference: str = Field(
        min_length=1,
        max_length=100,
    )

    amount: str = Field(
        min_length=1,
        max_length=100,
    )

    currency: str = Field(
        default="USD",
        min_length=3,
        max_length=3,
    )

    bank_address: str | None = Field(
        default=None,
        pattern=r"^0x[a-fA-F0-9]{40}$",
    )

    external_reference: str | None = Field(
        default=None,
        max_length=255,
    )
