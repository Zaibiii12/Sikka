from pydantic import BaseModel, Field


class TokenAccountAmountRequest(BaseModel):
    address: str
    amount: int = Field(gt=0)


class TokenAccountRequest(BaseModel):
    address: str
