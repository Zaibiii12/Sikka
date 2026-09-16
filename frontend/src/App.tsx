import {
  useCallback,
  useEffect,
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

import type {
  Bank,
  IndexedPayment,
  IndexerStatus,
  NetworkHealth,
  PublicConfig,
  TokenBalance,
} from "./types";


function short(value: string): string {
  if (value.length <= 14) {
    return value;
  }

  return (
    value.slice(0, 6)
    + "..."
    + value.slice(-4)
  );
}


function App() {
  const [
    config,
    setConfig,
  ] = useState<PublicConfig | null>(null);

  const [
    health,
    setHealth,
  ] = useState<NetworkHealth | null>(null);

  const [
    indexer,
    setIndexer,
  ] = useState<IndexerStatus | null>(null);

  const [
    banks,
    setBanks,
  ] = useState<Bank[]>([]);

  const [
    payments,
    setPayments,
  ] = useState<IndexedPayment[]>([]);

  const [
    walletAddress,
    setWalletAddress,
  ] = useState("");

  const [
    walletBank,
    setWalletBank,
  ] = useState<Bank | null>(null);

  const [
    balance,
    setBalance,
  ] = useState<TokenBalance | null>(null);

  const [
    nonce,
    setNonce,
  ] = useState<number | null>(null);

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


  const refreshSystem = useCallback(
    async () => {
      try {
        const [
          nextHealth,
          nextIndexer,
          nextBanks,
          nextPayments,
        ] = await Promise.all([
          api.health(),
          api.indexerStatus(),
          api.banks(),
          api.payments(),
        ]);

        setHealth(nextHealth);
        setIndexer(nextIndexer);
        setBanks(nextBanks);
        setPayments(nextPayments.items);
      } catch (nextError) {
        setError(
          nextError instanceof Error
            ? nextError.message
            : String(nextError),
        );
      }
    },
    [],
  );


  const refreshWallet = useCallback(
    async (address: string) => {
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
          nextError instanceof Error
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

        await refreshSystem();
      } catch (nextError) {
        setError(
          nextError instanceof Error
            ? nextError.message
            : String(nextError),
        );
      }
    })();
  }, [refreshSystem]);


  useEffect(() => {
    const timer =
      window.setInterval(() => {
        void refreshSystem();

        if (walletAddress !== "") {
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
    refreshWallet,
    walletAddress,
  ]);


  async function handleConnect() {
    try {
      setError("");

      const address =
        await connectWallet();

      setWalletAddress(address);

      await refreshWallet(address);
    } catch (nextError) {
      setError(
        nextError instanceof Error
          ? nextError.message
          : String(nextError),
      );
    }
  }


  async function handlePayment() {
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
        "Checking allowance...",
      );

      await ensureAllowance(
        config.token.address,
        config.payment_processor_address,
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
        "Preparing payment...",
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
        "Confirm EIP-712 signature...",
      );

      const signature =
        await signPaymentTypedData(
          prepared.typed_data,
          walletAddress,
        );

      setStatus(
        "Relaying transaction...",
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
        "Waiting for indexer...",
      );

      await waitForIndexedPayment(
        paymentId,
      );

      setStatus(
        "Payment finalized and indexed.",
      );

      await refreshSystem();
      await refreshWallet(
        walletAddress,
      );
    } catch (nextError) {
      setStatus(
        "Payment failed.",
      );

      setError(
        nextError instanceof Error
          ? nextError.message
          : String(nextError),
      );
    } finally {
      setBusy(false);
    }
  }


  const recipients =
    banks.filter(
      (bank) =>
        bank.active
        && bank.address.toLowerCase()
          !== walletAddress.toLowerCase(),
    );


  return (
    <main className="app-shell">
      <header className="hero">
        <div>
          <p className="eyebrow">
            Permissioned EVM settlement network
          </p>

          <h1>
            BlockSikka
          </h1>

          <p className="hero-copy">
            SIKKA payments finalized by Besu QBFT
            and indexed into PostgreSQL.
          </p>
        </div>

        <button
          className="primary-button"
          onClick={() => {
            void handleConnect();
          }}
        >
          {walletAddress === ""
            ? "Connect wallet"
            : short(walletAddress)}
        </button>
      </header>


      {error !== "" && (
        <div className="error-banner">
          {error}
        </div>
      )}


      <section className="status-grid">
        <article className="stat-card">
          <span>
            QBFT
          </span>

          <strong>
            {health?.connected
              ? "Connected"
              : "Offline"}
          </strong>

          <small>
            Block{" "}
            {health?.latest_block ?? "-"}
          </small>
        </article>


        <article className="stat-card">
          <span>
            Validators
          </span>

          <strong>
            {health?.validators.length ?? "-"}
          </strong>

          <small>
            Peers{" "}
            {health?.peer_count ?? "-"}
          </small>
        </article>


        <article className="stat-card">
          <span>
            Indexer
          </span>

          <strong>
            {indexer?.caught_up
              ? "Caught up"
              : "Syncing"}
          </strong>

          <small>
            Lag{" "}
            {indexer?.lag_blocks ?? "-"}
          </small>
        </article>


        <article className="stat-card">
          <span>
            Asset
          </span>

          <strong>
            {config?.token.symbol ?? "SIKKA"}
          </strong>

          <small>
            Chain{" "}
            {config?.chain_id ?? 1337}
          </small>
        </article>
      </section>


      <section className="two-column">
        <article className="panel">
          <p className="eyebrow">
            Wallet
          </p>

          <h2>
            Bank account
          </h2>

          {walletAddress === "" ? (
            <p className="muted">
              Connect Bank A to begin.
            </p>
          ) : (
            <div className="wallet-details">
              <div>
                <span>
                  Address
                </span>

                <code>
                  {walletAddress}
                </code>
              </div>

              <div>
                <span>
                  Bank
                </span>

                <strong>
                  {walletBank !== null
                    ? walletBank.name
                    : "Not registered"}
                </strong>
              </div>

              <div>
                <span>
                  Balance
                </span>

                <strong>
                  {balance !== null
                    ? String(
                        balance.display,
                      ) + " SIKKA"
                    : "-"}
                </strong>
              </div>

              <div>
                <span>
                  Nonce
                </span>

                <strong>
                  {nonce ?? "-"}
                </strong>
              </div>
            </div>
          )}
        </article>


        <article className="panel">
          <p className="eyebrow">
            Payment
          </p>

          <h2>
            Send SIKKA
          </h2>

          <label>
            Recipient

            <select
              value={recipient}
              disabled={
                busy
                || walletAddress === ""
              }
              onChange={(event) => {
                setRecipient(
                  event.target.value,
                );
              }}
            >
              <option value="">
                Select bank
              </option>

              {recipients.map(
                (bank) => (
                  <option
                    key={bank.address}
                    value={bank.address}
                  >
                    {bank.name}
                    {" - "}
                    {short(
                      bank.address,
                    )}
                  </option>
                ),
              )}
            </select>
          </label>


          <label>
            Amount

            <input
              type="number"
              min="0.000001"
              step="0.000001"
              value={amount}
              disabled={busy}
              onChange={(event) => {
                setAmount(
                  event.target.value,
                );
              }}
            />
          </label>


          <button
            className="primary-button full-width"
            disabled={
              busy
              || walletAddress === ""
              || recipient === ""
            }
            onClick={() => {
              void handlePayment();
            }}
          >
            {busy
              ? "Processing..."
              : "Sign & send payment"}
          </button>

          <p className="payment-status">
            {status}
          </p>
        </article>
      </section>


      <section className="panel">
        <div className="panel-title">
          <div>
            <p className="eyebrow">
              Indexed history
            </p>

            <h2>
              Recent payments
            </h2>
          </div>

          <button
            className="secondary-button"
            onClick={() => {
              void refreshSystem();
            }}
          >
            Refresh
          </button>
        </div>


        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>
                  Payment
                </th>

                <th>
                  From
                </th>

                <th>
                  To
                </th>

                <th>
                  Amount
                </th>

                <th>
                  Block
                </th>
              </tr>
            </thead>

            <tbody>
              {payments.map(
                (payment) => (
                  <tr
                    key={payment.payment_id}
                  >
                    <td>
                      <code>
                        {short(
                          payment.payment_id,
                        )}
                      </code>
                    </td>

                    <td>
                      {short(
                        payment.from_address,
                      )}
                    </td>

                    <td>
                      {short(
                        payment.to_address,
                      )}
                    </td>

                    <td>
                      {String(
                        payment.amount,
                      )}
                    </td>

                    <td>
                      {payment.block_number}
                    </td>
                  </tr>
                ),
              )}

              {payments.length === 0 && (
                <tr>
                  <td
                    colSpan={5}
                    className="empty"
                  >
                    No indexed payments.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>


      <footer>
        <span>
          BlockSikka development network
        </span>

        <span>
          Chain ID{" "}
          {config?.chain_id ?? 1337}
        </span>
      </footer>
    </main>
  );
}


export default App;
