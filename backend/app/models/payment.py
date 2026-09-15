from pydantic import BaseModel, Field


class PaymentOrderRequest(BaseModel):
    from_address: str
    to_address: str

    amount: int = Field(gt=0)
    nonce: int = Field(ge=0)
    expiry: int = Field(gt=0)

    payment_id: str


class PreparePaymentRequest(BaseModel):
    from_address: str
    to_address: str

    amount: int = Field(gt=0)
    expiry: int = Field(gt=0)

    payment_id: str


class RelayPaymentRequest(BaseModel):
    order: PaymentOrderRequest
    signature: str
