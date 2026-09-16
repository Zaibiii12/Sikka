export interface TokenConfig {
  address: string;
  name: string;
  symbol: string;
  decimals: number;
}

export interface PublicConfig {
  chain_id: number;
  network_name: string;
  payment_processor_address: string;
  bank_registry_address: string;
  token: TokenConfig;
}

export interface NetworkHealth {
  api: string;
  blockchain: string;
  connected: boolean;
  chain_id: number;
  expected_chain_id: number;
  latest_block: number;
  peer_count: number;
  validators: string[];
  syncing: boolean;
}

export interface IndexerStatus {
  initialized: boolean;
  chain_head: number;
  target_block: number;
  last_indexed_block: number | null;
  last_indexed_block_hash: string | null;
  lag_blocks: number | null;
  caught_up: boolean;
  start_block: number;
  confirmations: number;
  updated_at?: string | null;
}

export interface Bank {
  address: string;
  name: string;
  active: boolean;
  registered_at: number;
}

export interface TokenBalance {
  address: string;
  raw: number;
  decimals: number;
  display: number;
}

export interface PaymentOrder {
  from_address: string;
  to_address: string;
  amount: number;
  nonce: number;
  expiry: number;
  payment_id: string;
}

export interface TypedField {
  name: string;
  type: string;
}

export interface PaymentTypedData {
  types: Record<string, TypedField[]>;

  primaryType: string;

  domain: {
    name: string;
    version: string;
    chainId: number;
    verifyingContract: string;
  };

  message: {
    from: string;
    to: string;
    amount: number;
    nonce: number;
    expiry: number;
    paymentId: string;
  };
}

export interface PreparedPayment {
  order: PaymentOrder;
  typed_data: PaymentTypedData;
}

export interface RelayResponse {
  transaction_hash: string;
  sender: string;
  status: string;
}

export interface TransactionStatus {
  transaction_hash: string;
  status: "pending" | "success" | "failed";
  block_number?: number;
  gas_used?: number;
  from?: string;
  to?: string | null;
  nonce?: number;
}

export interface IndexedPayment {
  payment_id: string;
  from_address: string;
  to_address: string;
  amount: number;
  nonce: number;
  transaction_hash: string;
  block_number: number;
  block_timestamp: string;
  settled?: boolean;
  settlement_batch_id?: string | null;
}

export interface IndexedSettlement {
  batch_id: string;
  payment_count: number;
  payment_ids: string[];
  settled_by: string;
  transaction_hash: string;
  block_number: number;
  settled_at: string;
}

export interface ListResponse<T> {
  count: number;
  limit?: number;
  offset?: number;
  items: T[];
}
