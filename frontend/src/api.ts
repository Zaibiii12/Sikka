import { PUBLIC_DEMO } from "./publicDemo";

import type {
  Bank,
  IndexedPayment,
  IndexedSettlement,
  IndexerStatus,
  ListResponse,
  NetworkHealth,
  PaymentOrder,
  PreparedPayment,
  PublicConfig,
  RelayResponse,
  TokenBalance,
  TransactionStatus,
  TreasuryExceptionReport,
  TreasuryMintRequest,
  TreasuryMintRequestList,
  TreasuryMovementList,
  TreasuryOnchain,
  TreasuryReconciliationHistoryList,
  TreasuryReconciliation,
  TreasuryRecoveryStatus,
  TreasuryRedemption,
  TreasuryRedemptionList,
  TreasuryReserve,
} from "./types";


const API_BASE =
  import.meta.env.VITE_API_BASE_URL
  ?? "http://127.0.0.1:8000/api/v1";


const AUTH_TOKEN_STORAGE_KEY =
  "blocksikka.auth.token";


function authorizationHeaders():
Record<string, string> {
  if (PUBLIC_DEMO) {
    return {};
  }

  if (
    typeof window
    === "undefined"
  ) {
    return {};
  }

  try {
    const token =
      window.localStorage
        .getItem(
          AUTH_TOKEN_STORAGE_KEY,
        )
        ?.trim();

    if (!token) {
      return {};
    }

    return {
      Authorization:
        `Bearer ${token}`,
    };
  } catch {
    return {};
  }
}


async function request<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const method =
    (options?.method ?? "GET")
      .toUpperCase();

  if (
    PUBLIC_DEMO
    && ![
      "GET",
      "HEAD",
      "OPTIONS",
    ].includes(method)
  ) {
    throw new Error(
      "This deployment is read-only.",
    );
  }

  const response = await fetch(
    `${API_BASE}${path}`,
    {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(options?.headers ?? {}),
      },
    },
  );

  if (!response.ok) {
    let message =
      `${response.status} ${response.statusText}`;

    try {
      const body = await response.json();

      if (body?.detail) {
        message = String(body.detail);
      }
    } catch {
      // Keep HTTP status message.
    }

    throw new Error(message);
  }

  return response.json() as Promise<T>;
}


export const api = {
  publicConfig(): Promise<PublicConfig> {
    return request("/config/public");
  },

  health(): Promise<NetworkHealth> {
    return request("/health");
  },

  indexerStatus(): Promise<IndexerStatus> {
    return request("/indexer/status");
  },

  banks(): Promise<Bank[]> {
    return request("/banks");
  },

  bank(address: string): Promise<Bank> {
    return request(`/banks/${address}`);
  },

  balance(
    address: string,
  ): Promise<TokenBalance> {
    return request(
      `/token/balance/${address}`,
    );
  },

  nonce(
    address: string,
  ): Promise<{
    address: string;
    nonce: number;
  }> {
    return request(
      `/payments/nonce/${address}`,
    );
  },

  preparePayment(
    body: {
      from_address: string;
      to_address: string;
      amount: string;
      expiry: number;
      payment_id: string;
    },
  ): Promise<PreparedPayment> {
    return request(
      "/payments/prepare",
      {
        method: "POST",
        headers:
          authorizationHeaders(),
        body: JSON.stringify(body),
      },
    );
  },

  relayPayment(
    body: {
      order: PaymentOrder;
      signature: string;
    },
  ): Promise<RelayResponse> {
    return request(
      "/payments/relay",
      {
        method: "POST",
        headers:
          authorizationHeaders(),
        body: JSON.stringify(body),
      },
    );
  },

  transaction(
    hash: string,
  ): Promise<TransactionStatus> {
    return request(
      `/transactions/${hash}`,
    );
  },

  payments():
  Promise<ListResponse<IndexedPayment>> {
    return request(
      "/history/payments?limit=20",
    );
  },

  payment(
    paymentId: string,
  ): Promise<IndexedPayment> {
    return request(
      `/history/payments/${paymentId}`,
    );
  },

  settlements():
  Promise<ListResponse<IndexedSettlement>> {
    return request(
      "/history/settlements?limit=20",
    );
  },

  settlementPaymentStatus(
    paymentId: string,
  ): Promise<{
    payment_id: string;
    settled: boolean;
  }> {
    return request(
      `/settlements/payment/${paymentId}`,
    );
  },

  createSettlement(
    body: {
      batch_id: string;
      payment_ids: string[];
    },
  ): Promise<RelayResponse> {
    return request(
      "/settlements",
      {
        method: "POST",
        headers:
          authorizationHeaders(),
        body: JSON.stringify(body),
      },
    );
  },

  treasuryReserve():
  Promise<TreasuryReserve> {
    return request(
      "/treasury/reserve",
    );
  },

  treasuryOnchain():
  Promise<TreasuryOnchain> {
    return request(
      "/treasury/onchain",
    );
  },

  treasuryMovements():
  Promise<TreasuryMovementList> {
    return request(
      "/treasury/movements?limit=20",
    );
  },

  treasuryReconciliationHistory():
  Promise<TreasuryReconciliationHistoryList> {
    return request(
      "/treasury/reconciliation/history?limit=20",
    );
  },

  treasuryMintRequests():
  Promise<TreasuryMintRequestList> {
    return request(
      "/treasury/mint-requests?limit=20",
    );
  },

  treasuryMintRequest(
    requestId: string,
  ): Promise<TreasuryMintRequest> {
    return request(
      `/treasury/mint-requests/${requestId}`,
    );
  },

  treasuryRedemptions():
  Promise<TreasuryRedemptionList> {
    return request(
      "/treasury/redemptions?limit=20",
    );
  },

  treasuryRedemption(
    requestId: string,
  ): Promise<TreasuryRedemption> {
    return request(
      `/treasury/redemptions/${requestId}`,
    );
  },

  treasuryReconciliation():
  Promise<TreasuryReconciliation> {
    return request(
      "/treasury/reconciliation",
    );
  },

  treasuryExceptions():
  Promise<TreasuryExceptionReport> {
    return request(
      "/treasury/exceptions",
    );
  },

  treasuryRecoveryStatus():
  Promise<TreasuryRecoveryStatus> {
    return request(
      "/treasury/recovery/status",
    );
  },
};


export async function waitForTransaction(
  hash: string,
  attempts = 60,
): Promise<TransactionStatus> {
  for (
    let attempt = 0;
    attempt < attempts;
    attempt += 1
  ) {
    try {
      const status =
        await api.transaction(hash);

      if (
        status.status === "success"
        || status.status === "failed"
      ) {
        return status;
      }
    } catch {
      // Transaction may not be available yet.
    }

    await new Promise(
      (resolve) =>
        setTimeout(resolve, 1000),
    );
  }

  throw new Error(
    "Timed out waiting for transaction finality.",
  );
}


export async function waitForIndexedPayment(
  paymentId: string,
  attempts = 60,
): Promise<IndexedPayment> {
  for (
    let attempt = 0;
    attempt < attempts;
    attempt += 1
  ) {
    try {
      return await api.payment(
        paymentId,
      );
    } catch {
      // Indexer has not reached it yet.
    }

    await new Promise(
      (resolve) =>
        setTimeout(resolve, 1000),
    );
  }

  throw new Error(
    "Payment finalized, but was not indexed in time.",
  );
}
