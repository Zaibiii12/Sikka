import {
  keccak256,
  toUtf8Bytes,
} from "ethers";

import type {
  PreparedPayment,
  PublicConfig,
} from "./types";


export function createPaymentId(
  from: string,
  to: string,
): string {
  return keccak256(
    toUtf8Bytes(
      [
        "blocksikka-ui",
        from,
        to,
        Date.now().toString(),
        crypto.randomUUID(),
      ].join(":"),
    ),
  );
}


export function validatePreparedPayment(
  prepared: PreparedPayment,
  config: PublicConfig,
  expectedFrom: string,
  expectedTo: string,
  expectedAmount: bigint,
): void {
  const order = prepared.order;
  const typed = prepared.typed_data;

  if (
    order.from_address.toLowerCase()
    !== expectedFrom.toLowerCase()
  ) {
    throw new Error(
      "Prepared sender does not match the connected wallet.",
    );
  }

  if (
    order.to_address.toLowerCase()
    !== expectedTo.toLowerCase()
  ) {
    throw new Error(
      "Prepared recipient does not match the selected bank.",
    );
  }

  if (
    BigInt(order.amount)
    !== expectedAmount
  ) {
    throw new Error(
      "Prepared amount changed unexpectedly.",
    );
  }

  if (
    typed.domain.name
    !== "BlockSikka-PaymentProcessor"
  ) {
    throw new Error(
      "Unexpected EIP-712 domain.",
    );
  }

  if (
    Number(typed.domain.chainId)
    !== config.chain_id
  ) {
    throw new Error(
      "EIP-712 chain ID does not match BlockSikka.",
    );
  }

  if (
    typed.domain.verifyingContract.toLowerCase()
    !== config.payment_processor_address.toLowerCase()
  ) {
    throw new Error(
      "Unexpected PaymentProcessor address.",
    );
  }

  if (
    typed.message.from.toLowerCase()
    !== expectedFrom.toLowerCase()
  ) {
    throw new Error(
      "Typed-data sender changed unexpectedly.",
    );
  }

  if (
    typed.message.to.toLowerCase()
    !== expectedTo.toLowerCase()
  ) {
    throw new Error(
      "Typed-data recipient changed unexpectedly.",
    );
  }

  if (
    BigInt(typed.message.amount)
    !== expectedAmount
  ) {
    throw new Error(
      "Typed-data amount changed unexpectedly.",
    );
  }

  if (
    typed.message.paymentId
    !== order.payment_id
  ) {
    throw new Error(
      "Payment ID mismatch.",
    );
  }
}
