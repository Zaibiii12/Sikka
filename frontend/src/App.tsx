import {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  parseUnits,
} from "ethers";

import {
  api,
  waitForIndexedPayment,
  waitForTransaction,
} from "./api";

import {
  connectWallet,
  ensureAllowance,
  signPaymentTypedData,
} from "./wallet";

import {
  createPaymentId,
  validatePreparedPayment,
} from "./payment";

import {
  PUBLIC_DEMO,
  PUBLIC_DEMO_MESSAGE,
} from "./publicDemo";


import type {
  Bank,
  IndexedPayment,
  IndexedSettlement,
  IndexerStatus,
  NetworkHealth,
  PublicConfig,
  TokenBalance,
  TreasuryExceptionReport,
  TreasuryMintRequest,
  TreasuryMovement,
  TreasuryOnchain,
  TreasuryReconciliation,
  TreasuryReconciliationHistoryItem,
  TreasuryRecoveryStatus,
  TreasuryRedemption,
  TreasuryReserve,
} from "./types";

import Sidebar, {
  type AppView,
} from "./components/Sidebar";

import Topbar from "./components/Topbar";
import MetricCard from "./components/MetricCard";
import AccountSummary from "./components/AccountSummary";
import PaymentForm from "./components/PaymentForm";
import PaymentTrace from "./components/PaymentTrace";
import ActivityTable from "./components/ActivityTable";
import SettlementTable from "./components/SettlementTable";
import InstitutionDirectory from "./components/InstitutionDirectory";
import AddressDisplay from "./components/AddressDisplay";
import StatusBadge from "./components/StatusBadge";
import TreasuryView from "./components/TreasuryView";

import {
  formatDisplayAmount,
  formatInteger,
} from "./format";


const viewMeta: Record<
  AppView,
  {
    title: string;
    subtitle: string;
  }
> = {
  dashboard: {
    title: "Dashboard",
    subtitle:
      "Treasury overview and real-time settlement activity.",
  },

  payments: {
    title: "Payments",
    subtitle:
      "Authorize, sign and finalize institutional SIKKA transfers.",
  },

  settlements: {
    title: "Settlements",
    subtitle:
      "Review finalized settlement batches recorded on-chain.",
  },

  institutions: {
    title: "Institutions",
    subtitle:
      "Permissioned participants authorized on the BlockSikka settlement rail.",
  },

  treasury: {
    title: "Treasury",
    subtitle:
      "Reserve backing, issuance, redemption and reconciliation controls.",
  },

  network: {
    title: "Network",
    subtitle:
      "QBFT consensus, validator membership and indexing health.",
  },
};


export default function App() {
  const [
    activeView,
    setActiveView,
  ] = useState<AppView>(
    "dashboard",
  );

  const [
    config,
    setConfig,
  ] = useState<PublicConfig | null>(
    null,
  );

  const [
    health,
    setHealth,
  ] = useState<NetworkHealth | null>(
    null,
  );

  const [
    indexer,
    setIndexer,
  ] = useState<IndexerStatus | null>(
    null,
  );

  const [
    banks,
    setBanks,
  ] = useState<Bank[]>([]);

  const [
    payments,
    setPayments,
  ] = useState<IndexedPayment[]>([]);

  const [
    settlements,
    setSettlements,
  ] = useState<IndexedSettlement[]>([]);

  const [
    treasuryReserve,
    setTreasuryReserve,
  ] = useState<TreasuryReserve | null>(
    null,
  );

  const [
    treasuryOnchain,
    setTreasuryOnchain,
  ] = useState<TreasuryOnchain | null>(
    null,
  );

  const [
    treasuryMovements,
    setTreasuryMovements,
  ] = useState<TreasuryMovement[]>([]);

  const [
    treasuryReconciliationHistory,
    setTreasuryReconciliationHistory,
  ] = useState<TreasuryReconciliationHistoryItem[]>([]);

  const [
    treasuryMintRequests,
    setTreasuryMintRequests,
  ] = useState<TreasuryMintRequest[]>([]);

  const [
    treasuryRedemptions,
    setTreasuryRedemptions,
  ] = useState<TreasuryRedemption[]>([]);

  const [
    treasuryReconciliation,
    setTreasuryReconciliation,
  ] = useState<TreasuryReconciliation | null>(
    null,
  );

  const [
    treasuryExceptions,
    setTreasuryExceptions,
  ] = useState<TreasuryExceptionReport | null>(
    null,
  );

  const [
    treasuryRecovery,
    setTreasuryRecovery,
  ] = useState<TreasuryRecoveryStatus | null>(
    null,
  );


  const [
    walletAddress,
    setWalletAddress,
  ] = useState("");

  const [
    walletBank,
    setWalletBank,
  ] = useState<Bank | null>(
    null,
  );

  const [
    balance,
    setBalance,
  ] = useState<TokenBalance | null>(
    null,
  );

  const [
    nonce,
    setNonce,
  ] = useState<number | null>(
    null,
  );

  const [
    recipient,
    setRecipient,
  ] = useState("");

  const [
    amount,
    setAmount,
  ] = useState("1");

  const [
    status,
    setStatus,
  ] = useState("Ready.");

  const [
    error,
    setError,
  ] = useState("");

  const [
    busy,
    setBusy,
  ] = useState(false);


  const refreshSystem =
    useCallback(
      async () => {
        try {
          const [
            nextHealth,
            nextIndexer,
            nextBanks,
            nextPayments,
            nextSettlements,
          ] = await Promise.all([
            api.health(),
            api.indexerStatus(),
            api.banks(),
            api.payments(),
            api.settlements(),
          ]);

          setHealth(nextHealth);
          setIndexer(nextIndexer);
          setBanks(nextBanks);
          setPayments(
            nextPayments.items,
          );
          setSettlements(
            nextSettlements.items,
          );
        } catch (nextError) {
          setError(
            nextError
              instanceof Error
              ? nextError.message
              : String(nextError),
          );
        }
      },
      [],
    );


  const refreshTreasury =
    useCallback(
      async () => {
        try {
          const [
            nextReserve,
            nextOnchain,
            nextMovements,
            nextReconciliationHistory,
            nextMintRequests,
            nextRedemptions,
            nextReconciliation,
            nextExceptions,
            nextRecovery,
          ] = await Promise.all([
            api.treasuryReserve(),
            api.treasuryOnchain(),
            api.treasuryMovements(),
            api.treasuryReconciliationHistory(),
            api.treasuryMintRequests(),
            api.treasuryRedemptions(),
            api.treasuryReconciliation(),
            api.treasuryExceptions(),
            api.treasuryRecoveryStatus(),
          ]);

          setTreasuryReserve(
            nextReserve,
          );
          setTreasuryOnchain(
            nextOnchain,
          );
          setTreasuryMovements(
            nextMovements.items,
          );
          setTreasuryReconciliationHistory(
            nextReconciliationHistory.items,
          );
          setTreasuryMintRequests(
            nextMintRequests.items,
          );
          setTreasuryRedemptions(
            nextRedemptions.items,
          );
          setTreasuryReconciliation(
            nextReconciliation,
          );
          setTreasuryExceptions(
            nextExceptions,
          );
          setTreasuryRecovery(
            nextRecovery,
          );
        } catch (nextError) {
          setError(
            nextError
              instanceof Error
              ? nextError.message
              : String(nextError),
          );
        }
      },
      [],
    );


  const refreshWallet =
    useCallback(
      async (
        address: string,
      ) => {
        try {
          const [
            nextBalance,
            nextNonce,
          ] = await Promise.all([
            api.balance(address),
            api.nonce(address),
          ]);

          setBalance(nextBalance);
          setNonce(nextNonce.nonce);

          try {
            const bank =
              await api.bank(address);

            setWalletBank(bank);
          } catch {
            setWalletBank(null);
          }
        } catch (nextError) {
          setError(
            nextError
              instanceof Error
              ? nextError.message
              : String(nextError),
          );
        }
      },
      [],
    );


  useEffect(() => {
    void (async () => {
      try {
        const nextConfig =
          await api.publicConfig();

        setConfig(nextConfig);

        await Promise.all([
          refreshSystem(),
          refreshTreasury(),
        ]);
      } catch (nextError) {
        setError(
          nextError
            instanceof Error
            ? nextError.message
            : String(nextError),
        );
      }
    })();
  }, [
    refreshSystem,
    refreshTreasury,
  ]);


  useEffect(() => {
    const timer =
      window.setInterval(() => {
        void refreshSystem();
        void refreshTreasury();

        if (
          walletAddress !== ""
        ) {
          void refreshWallet(
            walletAddress,
          );
        }
      }, 5000);

    return () => {
      window.clearInterval(timer);
    };
  }, [
    refreshSystem,
    refreshTreasury,
    refreshWallet,
    walletAddress,
  ]);


  async function handleConnect() {
    if (PUBLIC_DEMO) {
      setError(
        PUBLIC_DEMO_MESSAGE,
      );
      return;
    }

    try {
      setError("");

      const address =
        await connectWallet();

      setWalletAddress(address);

      await refreshWallet(address);
    } catch (nextError) {
      setError(
        nextError
          instanceof Error
          ? nextError.message
          : String(nextError),
      );
    }
  }


  async function handlePayment() {
    if (PUBLIC_DEMO) {
      setError(
        PUBLIC_DEMO_MESSAGE,
      );
      return;
    }

    if (
      config === null
      || walletAddress === ""
    ) {
      setError(
        "Connect a wallet first.",
      );
      return;
    }

    if (
      walletBank === null
      || !walletBank.active
    ) {
      setError(
        "Connected wallet is not an active BlockSikka bank.",
      );
      return;
    }

    if (recipient === "") {
      setError(
        "Select a recipient.",
      );
      return;
    }

    try {
      setBusy(true);
      setError("");

      const amountBase =
        parseUnits(
          amount,
          config.token.decimals,
        );

      if (amountBase <= 0n) {
        throw new Error(
          "Amount must be greater than zero.",
        );
      }

      setStatus(
        "Checking token allowance...",
      );

      await ensureAllowance(
        config.token.address,
        config
          .payment_processor_address,
        walletAddress,
        amountBase,
      );

      const paymentId =
        createPaymentId(
          walletAddress,
          recipient,
        );

      const expiry =
        Math.floor(
          Date.now() / 1000,
        ) + 3600;

      setStatus(
        "Preparing signed payment order...",
      );

      const prepared =
        await api.preparePayment({
          from_address:
            walletAddress,

          to_address:
            recipient,

          amount:
            amountBase.toString(),

          expiry,

          payment_id:
            paymentId,
        });

      validatePreparedPayment(
        prepared,
        config,
        walletAddress,
        recipient,
        amountBase,
      );

      setStatus(
        "Confirm EIP-712 signature in your wallet...",
      );

      const signature =
        await signPaymentTypedData(
          prepared.typed_data,
          walletAddress,
        );

      setStatus(
        "Relaying transaction to the network...",
      );

      const relay =
        await api.relayPayment({
          order:
            prepared.order,

          signature,
        });

      setStatus(
        "Waiting for QBFT finality...",
      );

      const transaction =
        await waitForTransaction(
          relay.transaction_hash,
        );

      if (
        transaction.status
        !== "success"
      ) {
        throw new Error(
          "Payment transaction failed.",
        );
      }

      setStatus(
        "Finalized. Waiting for indexer...",
      );

      await waitForIndexedPayment(
        paymentId,
      );

      setStatus(
        "Payment finalized and indexed.",
      );

      setAmount("1");
      setRecipient("");

      await refreshSystem();

      await refreshWallet(
        walletAddress,
      );
    } catch (nextError) {
      setStatus(
        "Payment failed.",
      );

      setError(
        nextError
          instanceof Error
          ? nextError.message
          : String(nextError),
      );
    } finally {
      setBusy(false);
    }
  }


  const recipients =
    useMemo(
      () =>
        banks.filter(
          (bank) =>
            bank.active
            && (
              bank.address
                .toLowerCase()
              !== walletAddress
                .toLowerCase()
            ),
        ),
      [
        banks,
        walletAddress,
      ],
    );


  const symbol =
    config?.token.symbol
    ?? "SIKKA";

  const decimals =
    config?.token.decimals
    ?? 6;

  const balanceDisplay =
    formatDisplayAmount(
      balance?.display,
      decimals,
    );

  const networkHealthy =
    Boolean(
      health?.connected
      && !health?.syncing
      && health.validators.length
        === 4,
    );

  const indexerLag =
    indexer?.lag_blocks
    ?? null;

  const indexerHealthy =
    indexerLag !== null
    && indexerLag <= 1;

  const meta =
    viewMeta[activeView];


  function renderDashboard() {
    return (
      <>
        <section className="metric-grid">
          <MetricCard
            label="Available balance"
            value={
              <>
                {balanceDisplay}
                <span className="metric-unit">
                  {symbol}
                </span>
              </>
            }
            meta={
              walletBank?.name
              ?? (
                walletAddress
                  ? "Wallet connected"
                  : "Connect a wallet"
              )
            }
          />

          <MetricCard
            label="Network"
            value={
              networkHealthy
                ? "Operational"
                : "Attention"
            }
            status={
              networkHealthy
                ? "Healthy"
                : "Check"
            }
            tone={
              networkHealthy
                ? "success"
                : "warning"
            }
            meta={
              `Block ${
                formatInteger(
                  health?.latest_block,
                )
              }`
            }
          />

          <MetricCard
            label="Indexer"
            value={
              indexerLag === 0
                ? "Synchronized"
                : indexerLag === 1
                  ? "Near real-time"
                  : "Syncing"
            }
            status={
              indexerHealthy
                ? "Healthy"
                : "Lagging"
            }
            tone={
              indexerHealthy
                ? "success"
                : "warning"
            }
            meta={
              `Lag ${
                indexer?.lag_blocks
                ?? "—"
              } blocks`
            }
          />

          <MetricCard
            label="Validators"
            value={
              health?.validators
                .length
              ?? "—"
            }
            status="QBFT"
            tone="info"
            meta={
              `${
                health?.peer_count
                ?? "—"
              } peers visible`
            }
          />
        </section>

        <section className="primary-grid">
          <AccountSummary
            walletAddress={
              walletAddress
            }
            bank={walletBank}
            balance={
              balanceDisplay
            }
            symbol={symbol}
            nonce={nonce}
          />

          <PaymentForm
            recipients={recipients}
            recipient={recipient}
            amount={amount}
            symbol={symbol}
            status={status}
            busy={busy}
            readOnly={PUBLIC_DEMO}
            connected={
              walletAddress !== ""
            }
            onRecipientChange={
              setRecipient
            }
            onAmountChange={
              setAmount
            }
            onSubmit={() => {
              void handlePayment();
            }}
          />
        </section>

        <ActivityTable
          payments={payments}
          banks={banks}
          walletAddress={
            walletAddress
          }
          decimals={decimals}
          symbol={symbol}
          limit={8}
        />
      </>
    );
  }


  function renderPayments() {
    return (
      <>
        <section className="payments-workspace">
          <PaymentForm
            recipients={recipients}
            recipient={recipient}
            amount={amount}
            symbol={symbol}
            status={status}
            busy={busy}
            readOnly={PUBLIC_DEMO}
            connected={
              walletAddress !== ""
            }
            onRecipientChange={
              setRecipient
            }
            onAmountChange={
              setAmount
            }
            onSubmit={() => {
              void handlePayment();
            }}
          />

          <AccountSummary
            walletAddress={
              walletAddress
            }
            bank={walletBank}
            balance={
              balanceDisplay
            }
            symbol={symbol}
            nonce={nonce}
          />
        </section>

        {!PUBLIC_DEMO && (
          <PaymentTrace status={status} />
        )}

        <ActivityTable
          payments={payments}
          banks={banks}
          walletAddress={
            walletAddress
          }
          decimals={decimals}
          symbol={symbol}
          limit={12}
        />
      </>
    );
  }


  function renderSettlements() {
    return (
      <>
        <section className="metric-grid">
          <MetricCard
            label="Indexed batches"
            value={
              settlements.length
            }
            meta="SettlementEngine history"
          />

          <MetricCard
            label="Finalized payments"
            value={
              settlements.reduce(
                (
                  total,
                  settlement,
                ) =>
                  total
                  + settlement.payment_count,
                0,
              )
            }
            status="On-chain"
            tone="success"
            meta="Marked settled by indexer"
          />

          <MetricCard
            label="Latest block"
            value={
              formatInteger(
                health?.latest_block,
              )
            }
            meta={
              `Chain ${
                config?.chain_id
                ?? 1337
              }`
            }
          />

          <MetricCard
            label="Indexer lag"
            value={
              `${
                indexer?.lag_blocks
                ?? "—"
              }`
            }
            status={
              indexerLag === 0
                ? "Synced"
                : indexerLag === 1
                  ? "Near live"
                  : "Lagging"
            }
            tone={
              indexerHealthy
                ? "success"
                : "warning"
            }
            meta="blocks"
          />
        </section>

        <SettlementTable
          settlements={settlements}
          payments={payments}
          onCreated={refreshSystem}
        />
      </>
    );
  }


  function renderInstitutions() {
    const activeInstitutions =
      banks.filter(
        (bank) => bank.active,
      ).length;

    const inactiveInstitutions =
      banks.length
      - activeInstitutions;

    return (
      <>
        <section className="metric-grid">
          <MetricCard
            label="Registered institutions"
            value={banks.length}
            meta="BankRegistry participants"
          />

          <MetricCard
            label="Active institutions"
            value={activeInstitutions}
            status="Authorized"
            tone="success"
            meta="Eligible for payments"
          />

          <MetricCard
            label="Inactive institutions"
            value={inactiveInstitutions}
            status={
              inactiveInstitutions === 0
                ? "None"
                : "Restricted"
            }
            tone={
              inactiveInstitutions === 0
                ? "success"
                : "warning"
            }
            meta="Not eligible for payments"
          />

          <MetricCard
            label="Onboarding control"
            value="BANK ADMIN"
            status="Permissioned"
            tone="info"
            meta="Governed institution enrollment"
          />
        </section>

        <InstitutionDirectory
          banks={banks}
          connectedAddress={
            walletAddress
          }
        />
      </>
    );
  }


  function renderTreasury() {
    return (
      <TreasuryView
        reserve={treasuryReserve}
        onchain={treasuryOnchain}
        movements={
          treasuryMovements
        }
        reconciliationHistory={
          treasuryReconciliationHistory
        }
        mintRequests={
          treasuryMintRequests
        }
        redemptions={
          treasuryRedemptions
        }
        reconciliation={
          treasuryReconciliation
        }
        exceptions={
          treasuryExceptions
        }
        recovery={
          treasuryRecovery
        }
        banks={banks}
      />
    );
  }


  function renderNetwork() {
    return (
      <>
        <section className="metric-grid">
          <MetricCard
            label="Consensus"
            value={
              health?.connected
                ? "QBFT online"
                : "Offline"
            }
            status={
              networkHealthy
                ? "Healthy"
                : "Attention"
            }
            tone={
              networkHealthy
                ? "success"
                : "warning"
            }
            meta={
              config?.network_name
              ?? "BlockSikka"
            }
          />

          <MetricCard
            label="Chain ID"
            value={
              config?.chain_id
              ?? "—"
            }
            meta="Permissioned EVM"
          />

          <MetricCard
            label="Block height"
            value={
              formatInteger(
                health?.latest_block,
              )
            }
            meta={
              health?.syncing
                ? "Node synchronizing"
                : "Node synchronized"
            }
          />

          <MetricCard
            label="Indexer"
            value={
              indexerLag === 0
                ? "Caught up"
                : indexerLag === 1
                  ? "Near real-time"
                  : "Syncing"
            }
            status={
              indexerHealthy
                ? "Healthy"
                : "Lagging"
            }
            tone={
              indexerHealthy
                ? "success"
                : "warning"
            }
            meta={
              `Checkpoint ${
                formatInteger(
                  indexer
                    ?.last_indexed_block,
                )
              }`
            }
          />
        </section>

        <section className="network-grid">
          <article className="surface">
            <div className="surface-heading">
              <div>
                <span className="section-kicker">
                  Consensus
                </span>

                <h2>
                  Validator network
                </h2>
              </div>

              <StatusBadge
                label={
                  networkHealthy
                    ? "Operational"
                    : "Attention"
                }
                tone={
                  networkHealthy
                    ? "success"
                    : "warning"
                }
              />
            </div>

            <div className="validator-list">
              {health?.validators
                .map(
                  (
                    validator,
                    index,
                  ) => (
                    <div
                      className="validator-row"
                      key={validator}
                    >
                      <div className="validator-number">
                        {index + 1}
                      </div>

                      <div>
                        <strong>
                          Validator {
                            index + 1
                          }
                        </strong>

                        <AddressDisplay
                          value={validator}
                          compact
                        />
                      </div>

                      <StatusBadge
                        label="Active"
                        tone="success"
                      />
                    </div>
                  ),
                )
              ?? (
                <p className="empty-copy">
                  Validator membership
                  unavailable.
                </p>
              )}
            </div>
          </article>

          <article className="surface">
            <div className="surface-heading">
              <div>
                <span className="section-kicker">
                  Infrastructure
      </span>

                <h2>
                  Chain configuration
                </h2>
              </div>
            </div>

            <dl className="detail-list">
              <div>
                <dt>Network</dt>
                <dd>
                  {config?.network_name
                    ?? "—"}
                </dd>
              </div>

              <div>
                <dt>Chain ID</dt>
                <dd>
                  {config?.chain_id
                    ?? "—"}
                </dd>
              </div>

              <div>
                <dt>
                  Visible peers
                </dt>
                <dd>
                  {health?.peer_count
                    ?? "—"}
                </dd>
              </div>

              <div>
                <dt>
                  Latest block
                </dt>
                <dd>
                  {formatInteger(
                    health
                      ?.latest_block,
                  )}
                </dd>
              </div>

              <div>
                <dt>
                  Indexer target
                </dt>
                <dd>
                  {formatInteger(
                    indexer
                      ?.target_block,
                  )}
                </dd>
              </div>

              <div>
                <dt>
                  Confirmations
                </dt>
                <dd>
                  {indexer
                    ?.confirmations
                    ?? "—"}
                </dd>
              </div>
            </dl>
          </article>
        </section>
      </>
    );
  }


  return (
    <div className="app-frame">
      <Sidebar
        activeView={activeView}
        onChange={setActiveView}
        networkHealthy={
          networkHealthy
        }
      />

      <div className="workspace">
        <Topbar
          title={meta.title}
          subtitle={meta.subtitle}
          walletAddress={
            walletAddress
          }
          bankName={
            walletBank?.name
          }
          readOnly={PUBLIC_DEMO}
          onConnect={() => {
            void handleConnect();
          }}
        />

        <main className="workspace-content">
          {error !== "" && (
            <div
              className="alert-banner"
              role="alert"
            >
              <div>
                <strong>
                  Action required
                </strong>

                <p>{error}</p>
              </div>

              <button
                type="button"
                onClick={() => {
                  setError("");
                }}
                aria-label="Dismiss error"
              >
                Dismiss
              </button>
            </div>
          )}

          {activeView
            === "dashboard"
            && renderDashboard()}

          {activeView
            === "payments"
            && renderPayments()}

          {activeView
            === "settlements"
            && renderSettlements()}

          {activeView
            === "institutions"
            && renderInstitutions()}

          {activeView
            === "network"
            && renderNetwork()}
          {activeView === "treasury"
            && renderTreasury()}

        </main>

        <footer className="workspace-footer">
          <span>
            BlockSikka development network
          </span>

          <span>
            Chain ID{" "}
            {config?.chain_id
              ?? 1337}
          </span>
        </footer>
      </div>
    </div>
  );
}
