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


export interface TreasuryReserve {
  currency: string;
  source_type: string;
  verified_balance_micro: string;
  reserved_balance_micro: string;
  available_balance_micro: string;
  verified_balance_display: string;
  reserved_balance_display: string;
  available_balance_display: string;
  version: number;
  updated_at: string;
}


export interface TreasuryOnchain {
  controller_address: string;
  verified_reserve_micro: string;
  total_supply_micro: string;
  available_mint_capacity_micro: string;
  reserve_deficit_micro: string;
  verified_reserve_display: string;
  total_supply_display: string;
  available_mint_capacity_display: string;
  reserve_deficit_display: string;
  reserve_attestor: string;
  treasury_operator: string;
  fully_backed: boolean;
}


export interface TreasuryMintRequest {
  request_id: string;
  bank_address: string;
  currency: string;
  amount_micro: string;
  amount_display: string;
  status: string;
  reserve_movement_id: number | null;
  transaction_hash: string | null;
  block_number: number | null;
  failure_reason: string | null;
  created_at: string;
  updated_at: string;
}


export interface TreasuryMintRequestList {
  count: number;
  limit: number;
  offset: number;
  items: TreasuryMintRequest[];
}


export interface TreasuryRedemption {
  request_id: string;
  bank_address: string;
  currency: string;
  amount_micro: string;
  amount_display: string;
  status: string;
  payout_movement_id: number | null;
  transaction_hash: string | null;
  block_number: number | null;
  failure_reason: string | null;
  created_at: string;
  updated_at: string;
}


export interface TreasuryRedemptionList {
  count: number;
  limit: number;
  offset: number;
  items: TreasuryRedemption[];
}


export interface TreasuryReconciliation {
  currency: string;
  database_verified_reserve_micro: string;
  database_reserved_micro: string;
  onchain_verified_reserve_micro: string;
  total_supply_micro: string;
  available_mint_capacity_micro: string;
  reserve_deficit_micro: string;
  reserve_difference_micro: string;
  database_verified_reserve_display: string;
  onchain_verified_reserve_display: string;
  total_supply_display: string;
  reserve_difference_display: string;
  reserve_matches: boolean;
  fully_backed: boolean;
  clean: boolean;
}


export interface TreasuryExceptionReport {
  currency: string;
  checked_at: string;
  stale_minutes: number;
  clean: boolean;
  exception_count: number;
  exceptions: Record<string, unknown>[];
  reconciliation: TreasuryReconciliation;
}


export interface TreasuryRecoveryMintItem {
  request_id: string;
  status: string;
  transaction_hash: string | null;
}


export interface TreasuryRecoveryRedemptionItem {
  request_id: string;
  status: string;
  transaction_hash: string | null;
  payout_movement_id: number | null;
}


export interface TreasuryRecoveryStatus {
  mint_unresolved: number;
  redemption_unresolved: number;
  total_unresolved: number;
  mint_requests: TreasuryRecoveryMintItem[];
  redemption_requests: TreasuryRecoveryRedemptionItem[];
}


export interface TreasuryMovementDetails {
  source?: string;
  redemption_request_id?: string;
  reserve_attestation_id?: string;
  reserve_attestation_tx?: string;
  reserve_attestation_block?: number;
  [key: string]: unknown;
}


export interface TreasuryMovement {
  id: number;
  reference: string;
  movement_type: string;
  currency: string;
  amount_micro: string;
  amount_display: string;
  bank_address: string | null;
  status: string;
  external_reference: string | null;
  details: TreasuryMovementDetails;
  created_at: string;
  verified_at: string | null;
}


export interface TreasuryMovementList {
  count: number;
  limit: number;
  offset: number;
  items: TreasuryMovement[];
}


export interface TreasuryReconciliationHistoryItem {
  id: number;
  currency: string;
  reported_balance_micro: string;
  ledger_balance_micro: string;
  difference_micro: string;
  status: string;
  source_reference: string | null;
  created_at: string;
}


export interface TreasuryReconciliationHistoryList {
  count: number;
  limit: number;
  offset: number;
  items: TreasuryReconciliationHistoryItem[];
}
