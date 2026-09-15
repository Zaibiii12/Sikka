from app.core.config import get_settings
from app.core.contracts import get_contracts
from app.core.eip712 import build_payment_typed_data
from app.core.eth import (
    checksum_address,
    parse_bytes32,
    parse_hex_bytes,
)
from app.core.tx import TransactionSender
from app.models.payment import (
    PaymentOrderRequest,
    PreparePaymentRequest,
)


class PaymentService:
    def __init__(self) -> None:
        self.contract = get_contracts().payment_processor

    def nonce(self, address: str) -> int:
        address = checksum_address(address)

        return (
            self.contract.functions
            .nonces(address)
            .call()
        )

    def is_processed(self, payment_id: str) -> bool:
        payment_id_bytes = parse_bytes32(payment_id)

        return (
            self.contract.functions
            .isProcessed(payment_id_bytes)
            .call()
        )

    def prepare(
        self,
        request: PreparePaymentRequest,
    ) -> dict:
        settings = get_settings()

        from_address = checksum_address(
            request.from_address
        )
        to_address = checksum_address(
            request.to_address
        )

        # Validate bytes32 now, before handing anything
        # to a wallet.
        parse_bytes32(request.payment_id)

        nonce = self.nonce(from_address)

        typed_data = build_payment_typed_data(
            chain_id=settings.chain_id,
            verifying_contract=checksum_address(
                settings.payment_processor_address
            ),
            from_address=from_address,
            to_address=to_address,
            amount=request.amount,
            nonce=nonce,
            expiry=request.expiry,
            payment_id=request.payment_id,
        )

        return {
            "order": {
                "from_address": from_address,
                "to_address": to_address,
                "amount": request.amount,
                "nonce": nonce,
                "expiry": request.expiry,
                "payment_id": request.payment_id,
            },
            "typed_data": typed_data,
        }

    def relay(
        self,
        order: PaymentOrderRequest,
        signature: str,
    ) -> dict:
        from_address = checksum_address(
            order.from_address
        )
        to_address = checksum_address(
            order.to_address
        )

        payment_id = parse_bytes32(
            order.payment_id
        )

        signature_bytes = parse_hex_bytes(signature)

        if len(signature_bytes) != 65:
            raise ValueError(
                "Expected a standard 65-byte ECDSA signature"
            )

        order_tuple = (
            from_address,
            to_address,
            order.amount,
            order.nonce,
            order.expiry,
            payment_id,
        )

        function = (
            self.contract.functions
            .submitPayment(
                order_tuple,
                signature_bytes,
            )
        )

        return TransactionSender().send(
            function,
            wait=False,
        )
