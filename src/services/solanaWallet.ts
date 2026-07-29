import {
  Connection,
  PublicKey,
  SystemProgram,
  Transaction,
  TransactionInstruction,
} from '@solana/web3.js'
import { Buffer } from 'buffer'

const DEFAULT_SOLANA_RPC_URL = 'https://api.devnet.solana.com'
const JOIN_CONTEST_DISCRIMINATOR = Uint8Array.from([247, 243, 77, 111, 247, 254, 100, 133])
const textEncoder = new TextEncoder()

interface SolanaWalletProvider {
  isPhantom?: boolean
  isSolflare?: boolean
  publicKey?: PublicKey
  connect: () => Promise<{ publicKey: PublicKey }>
  signAndSendTransaction?: (transaction: Transaction) => Promise<{ signature: string }>
  signTransaction?: (transaction: Transaction) => Promise<Transaction>
}

declare global {
  interface Window {
    solana?: SolanaWalletProvider
  }
}

export interface JoinContestOnchainInput {
  contestId: string
  walletPublicKey?: string
}

export interface JoinContestOnchainResult {
  walletAddress: string
  signature: string
}

export interface ConnectSolanaWalletResult {
  walletAddress: string
  walletName: string
}

function solanaRpcUrl(): string {
  return import.meta.env.VITE_SOLANA_RPC_URL || DEFAULT_SOLANA_RPC_URL
}

function contestProgramId(): PublicKey {
  const value = import.meta.env.VITE_SOLANA_CONTEST_PROGRAM_ID
  if (!value) {
    throw new Error('Solana contest program is not configured')
  }
  return new PublicKey(value)
}

function solanaProvider(): SolanaWalletProvider {
  if (!window.solana) {
    throw new Error('Install Phantom or Solflare to join on Solana')
  }
  return window.solana
}

export async function connectSolanaWallet(): Promise<ConnectSolanaWalletResult> {
  const provider = solanaProvider()
  const connected = await provider.connect()
  return {
    walletAddress: connected.publicKey.toBase58(),
    walletName: walletProviderName(provider),
  }
}

export async function joinContestOnchain(
  input: JoinContestOnchainInput,
): Promise<JoinContestOnchainResult> {
  const provider = solanaProvider()
  const connected = await provider.connect()
  const wallet = connected.publicKey
  if (input.walletPublicKey && input.walletPublicKey !== wallet.toBase58()) {
    throw new Error('Connected wallet does not match the selected wallet')
  }

  const programId = contestProgramId()
  const contest = PublicKey.findProgramAddressSync(
    [textEncoder.encode('contest'), textEncoder.encode(input.contestId)],
    programId,
  )[0]
  const participant = PublicKey.findProgramAddressSync(
    [textEncoder.encode('participant'), contest.toBuffer(), wallet.toBuffer()],
    programId,
  )[0]
  const connection = new Connection(solanaRpcUrl(), 'confirmed')
  const transaction = new Transaction().add(
    new TransactionInstruction({
      programId,
      keys: [
        { pubkey: contest, isSigner: false, isWritable: false },
        { pubkey: participant, isSigner: false, isWritable: true },
        { pubkey: wallet, isSigner: true, isWritable: true },
        { pubkey: SystemProgram.programId, isSigner: false, isWritable: false },
      ],
      data: Buffer.from(JOIN_CONTEST_DISCRIMINATOR),
    }),
  )
  transaction.feePayer = wallet
  transaction.recentBlockhash = (await connection.getLatestBlockhash()).blockhash

  if (provider.signAndSendTransaction) {
    const { signature } = await provider.signAndSendTransaction(transaction)
    await connection.confirmTransaction(signature, 'confirmed')
    return { walletAddress: wallet.toBase58(), signature }
  }

  if (!provider.signTransaction) {
    throw new Error('Connected wallet cannot sign Solana transactions')
  }
  const signed = await provider.signTransaction(transaction)
  const signature = await connection.sendRawTransaction(signed.serialize())
  await connection.confirmTransaction(signature, 'confirmed')
  return { walletAddress: wallet.toBase58(), signature }
}

function walletProviderName(provider: SolanaWalletProvider): string {
  if (provider.isPhantom) return 'Phantom'
  if (provider.isSolflare) return 'Solflare'
  return 'Solana wallet'
}
