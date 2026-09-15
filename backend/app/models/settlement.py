from pydantic import BaseModel, Field


class CreateSettlementRequest(BaseModel):
    batch_id: str

    payment_ids: list[str] = Field(
        min_length=1,
        max_length=100,
    )
