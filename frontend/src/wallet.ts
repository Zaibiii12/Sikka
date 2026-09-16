import {
  BrowserProvider,
  Contract,
} from "ethers";

import type {
  PaymentTypedData,
} from "./types";


interface InjectedProvider {
  request(args: {
    method: string;
    params?:
      | readonly unknown[]
      | Record<string, unknown>;
  }): Promise<unknown>;
}


interface RpcErrorLike {
  code?: number;
  message?: string;
  data?: unknown;
}


declare global {
  interface Window {
    ethereum?: InjectedProvider;
  }
}


const CHAIN_ID = Number(
  import.meta.env.VITE_CHAIN_ID
  ?? 1337,
);

const CHAIN_ID_HEX =
  `0x${CHAIN_ID.toString(16)}`;

const CHAIN_NAME =
  import.meta.env.VITE_CHAIN_NAME
  ?? "BlockSikka Local";

const RPC_URL =
  import.meta.env.VITE_RPC_URL
  ?? "http://127.0.0.1:8547";


const ERC20_ABI = [
  "function allowance(address owner,address spender) view returns (uint256)",
  "function approve(address spender,uint256 amount) returns (bool)",
];


function injected(): InjectedProvider {
  if (!window.ethereum) {
    throw new Error(
      "No injected Ethereum wallet detected. "
      + "Install MetaMask or Rabby first.",
    );
  }

  return window.ethereum;
}


function asRpcError(
  error: unknown,
): RpcErrorLike | null {
  if (
    typeof error !== "object"
    || error === null
  ) {
    return null;
  }

  return error as RpcErrorLike;
}


function nestedErrorCode(
  value: unknown,
): number | undefined {
  if (
    typeof value !== "object"
    || value === null
  ) {
    return undefined;
  }

  if (
    "code" in value
    && typeof value.code === "number"
  ) {
    return value.code;
  }

  if ("originalError" in value) {
    return nestedErrorCode(
      value.originalError,
    );
  }

  return undefined;
}


function isUnknownChainError(
  error: unknown,
): boolean {
  const rpcError =
    asRpcError(error);

  if (!rpcError) {
    return false;
  }

  if (rpcError.code === 4902) {
    return true;
  }

  if (
    nestedErrorCode(
      rpcError.data,
    ) === 4902
  ) {
    return true;
  }

  const message =
    rpcError.message
      ?.toLowerCase()
      ?? "";

  return (
    message.includes(
      "unrecognized chain",
    )
    || message.includes(
      "unknown chain",
    )
    || message.includes(
      "chain has not been added",
    )
    || message.includes(
      "not added",
    )
  );
}


async function currentChainId():
Promise<string> {
  const ethereum =
    injected();

  const value =
    await ethereum.request({
      method: "eth_chainId",
    });

  return String(
    value,
  ).toLowerCase();
}


export async function ensureBlockSikkaNetwork():
Promise<void> {
  const ethereum =
    injected();

  const current =
    await currentChainId();

  if (
    current
    === CHAIN_ID_HEX.toLowerCase()
  ) {
    return;
  }

  try {
    await ethereum.request({
      method:
        "wallet_switchEthereumChain",

      params: [
        {
          chainId:
            CHAIN_ID_HEX,
        },
      ],
    });
  } catch (error) {
    if (
      !isUnknownChainError(
        error,
      )
    ) {
      throw error;
    }

    await ethereum.request({
      method:
        "wallet_addEthereumChain",

      params: [
        {
          chainId:
            CHAIN_ID_HEX,

          chainName:
            CHAIN_NAME,

          rpcUrls: [
            RPC_URL,
          ],

          nativeCurrency: {
            name:
              "Development Ether",

            symbol:
              "ETH",

            decimals:
              18,
          },
        },
      ],
    });

    await ethereum.request({
      method:
        "wallet_switchEthereumChain",

      params: [
        {
          chainId:
            CHAIN_ID_HEX,
        },
      ],
    });
  }

  const finalChainId =
    await currentChainId();

  if (
    finalChainId
    !== CHAIN_ID_HEX.toLowerCase()
  ) {
    throw new Error(
      "Wallet did not switch to "
      + `BlockSikka chain ${CHAIN_ID}.`,
    );
  }
}


export async function connectWallet():
Promise<string> {
  const ethereum =
    injected();

  await ethereum.request({
    method:
      "eth_requestAccounts",
  });

  await ensureBlockSikkaNetwork();

  const provider =
    new BrowserProvider(
      ethereum as never,
    );

  const signer =
    await provider.getSigner();

  return signer.getAddress();
}


async function signerFor(
  expectedAddress: string,
) {
  const ethereum =
    injected();

  await ensureBlockSikkaNetwork();

  const provider =
    new BrowserProvider(
      ethereum as never,
    );

  const signer =
    await provider.getSigner();

  const address =
    await signer.getAddress();

  if (
    address.toLowerCase()
    !== expectedAddress.toLowerCase()
  ) {
    throw new Error(
      "Connected wallet account changed. "
      + "Select the registered BlockSikka "
      + "bank account and reconnect.",
    );
  }

  return signer;
}


export async function ensureAllowance(
  tokenAddress: string,
  processorAddress: string,
  ownerAddress: string,
  requiredAmount: bigint,
): Promise<void> {
  const signer =
    await signerFor(
      ownerAddress,
    );

  const token =
    new Contract(
      tokenAddress,
      ERC20_ABI,
      signer,
    );

  const allowance =
    await token.allowance(
      ownerAddress,
      processorAddress,
    ) as bigint;

  if (
    allowance
    >= requiredAmount
  ) {
    return;
  }

  const transaction =
    await token.approve(
      processorAddress,
      requiredAmount,
    );

  const receipt =
    await transaction.wait();

  if (
    receipt === null
    || receipt.status !== 1
  ) {
    throw new Error(
      "SIKKA approval transaction failed.",
    );
  }
}


export async function signPaymentTypedData(
  typedData: PaymentTypedData,
  expectedAddress: string,
): Promise<string> {
  const signer =
    await signerFor(
      expectedAddress,
    );

  const types =
    Object.fromEntries(
      Object.entries(
        typedData.types,
      ).filter(
        ([typeName]) =>
          typeName
          !== "EIP712Domain",
      ),
    );

  return signer.signTypedData(
    typedData.domain,
    types,
    typedData.message,
  );
}
