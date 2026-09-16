from app.core.config import get_settings
from app.core.contracts import get_contracts
from app.core.eip712 import build_payment_typed_data
from app.core.eth import (
    bytes32_hex,
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
        self.contract = (
            get_contracts().payment_processor
        )
        self.settings = get_settings()

    def nonce(
        self,
        address: str,
    ) -> int:
        address = checksum_address(address)

        return (
            self.contract.functions
            .nonces(address)
            .call()
        )

    def is_processed(
        self,
        payment_id: str,
    ) -> bool:
        payment_id_bytes = parse_bytes32(
            payment_id
        )

        return (
            self.contract.functions
            .isProcessed(payment_id_bytes)
            .call()
        )

    def prepare(
        self,
        request: PreparePaymentRequest,
    ) -> dict:
        from_address = checksum_address(
            request.from_address
        )

        to_address = checksum_address(
            request.to_address
        )

        # Validate and normalize to a canonical 0x-prefixed
        # bytes32 value.
        payment_id = bytes32_hex(
            parse_bytes32(
                request.payment_id
            )
        )

        nonce = self.nonce(
            from_address
        )

        typed_data = build_payment_typed_data(
            chain_id=self.settings.chain_id,
            verifying_contract=checksum_address(
                self.settings
                .payment_processor_address
            ),
            from_address=from_address,
            to_address=to_address,
            amount=request.amount,
            nonce=nonce,
            expiry=request.expiry,
            payment_id=payment_id,
        )

        return {
            "order": {
                "from_address": from_address,
                "to_address": to_address,
                "amount": request.amount,
                "nonce": nonce,
                "expiry": request.expiry,
                "payment_id": payment_id,
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

        signature_bytes = parse_hex_bytes(
            signature
        )

        if len(signature_bytes) != 65:
            raise ValueError(
                "Expected a standard "
                "65-byte ECDSA signature"
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

        return TransactionSender(
            self.settings.relayer_private_key,
            "RELAYER_PRIVATE_KEY",
        ).send(
            function,
            wait=False,
        )
