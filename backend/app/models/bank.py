from pydantic import BaseModel, Field


class BankResponse(BaseModel):
    address: str
    name: str
    active: bool
    registered_at: int


class RegisterBankRequest(BaseModel):
    address: str
    name: str = Field(min_length=1, max_length=128)


class BankAddressRequest(BaseModel):
    address: str
