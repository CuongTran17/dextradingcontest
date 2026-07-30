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
const CLAIM_CERTIFICATE_DISCRIMINATOR = Uint8Array.from([45, 124, 106, 139, 156, 89, 153, 233])
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

export interface ClaimCertificateOnchainInput {
  contestId: string
  walletPublicKey: string
  rank: number
  metadataUri: string
  snapshotHash: string
  proof: string[]
}

export interface ClaimCertificateOnchainResult {
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

  const { signature } = await signAndConfirm(provider, connection, transaction)
  return { walletAddress: wallet.toBase58(), signature }
}

export async function claimCertificateOnchain(
  input: ClaimCertificateOnchainInput,
): Promise<ClaimCertificateOnchainResult> {
  const snapshotHash = hexToBytes32(input.snapshotHash, 'Snapshot hash')
  const proof = input.proof.map((item) => hexToBytes32(item, 'Merkle proof item'))
  if (!Number.isInteger(input.rank) || input.rank < 0 || input.rank > 255) {
    throw new Error('Certificate rank must fit in one byte')
  }

  const provider = solanaProvider()
  const connected = await provider.connect()
  const wallet = connected.publicKey
  if (input.walletPublicKey !== wallet.toBase58()) {
    throw new Error('Connected wallet does not match the selected wallet')
  }

  const programId = contestProgramId()
  const contest = PublicKey.findProgramAddressSync(
    [textEncoder.encode('contest'), textEncoder.encode(input.contestId)],
    programId,
  )[0]
  const certificate = PublicKey.findProgramAddressSync(
    [textEncoder.encode('certificate'), contest.toBuffer(), wallet.toBuffer()],
    programId,
  )[0]
  const data = encodeClaimCertificateInstruction({
    contestId: input.contestId,
    rank: input.rank,
    metadataUri: input.metadataUri,
    snapshotHash,
    proof,
  })
  const connection = new Connection(solanaRpcUrl(), 'confirmed')
  const transaction = new Transaction().add(
    new TransactionInstruction({
      programId,
      keys: [
        { pubkey: contest, isSigner: false, isWritable: false },
        { pubkey: certificate, isSigner: false, isWritable: true },
        { pubkey: wallet, isSigner: true, isWritable: true },
        { pubkey: SystemProgram.programId, isSigner: false, isWritable: false },
      ],
      data,
    }),
  )
  transaction.feePayer = wallet
  transaction.recentBlockhash = (await connection.getLatestBlockhash()).blockhash

  return signAndConfirm(provider, connection, transaction)
}

async function signAndConfirm(
  provider: SolanaWalletProvider,
  connection: Connection,
  transaction: Transaction,
): Promise<{ signature: string }> {
  if (provider.signAndSendTransaction) {
    const { signature } = await provider.signAndSendTransaction(transaction)
    await connection.confirmTransaction(signature, 'confirmed')
    return { signature }
  }

  if (!provider.signTransaction) {
    throw new Error('Connected wallet cannot sign Solana transactions')
  }
  const signed = await provider.signTransaction(transaction)
  const signature = await connection.sendRawTransaction(signed.serialize())
  await connection.confirmTransaction(signature, 'confirmed')
  return { signature }
}

function encodeClaimCertificateInstruction(input: {
  contestId: string
  rank: number
  metadataUri: string
  snapshotHash: number[]
  proof: number[][]
}): Buffer {
  return Buffer.concat([
    Buffer.from(CLAIM_CERTIFICATE_DISCRIMINATOR),
    encodeAnchorString(input.contestId),
    Buffer.from([input.rank]),
    encodeAnchorString(input.metadataUri),
    Buffer.from(input.snapshotHash),
    encodeAnchorVec32(input.proof),
  ])
}

function encodeAnchorString(value: string): Buffer {
  const content = Buffer.from(value, 'utf8')
  const length = Buffer.alloc(4)
  length.writeUInt32LE(content.length, 0)
  return Buffer.concat([length, content])
}

function encodeAnchorVec32(values: number[][]): Buffer {
  const length = Buffer.alloc(4)
  length.writeUInt32LE(values.length, 0)
  return Buffer.concat([length, ...values.map((item) => Buffer.from(item))])
}

function hexToBytes32(value: string, label: string): number[] {
  if (!/^[0-9a-fA-F]{64}$/.test(value)) {
    throw new Error(`${label} must be 32 bytes`)
  }
  const bytes: number[] = []
  for (let index = 0; index < value.length; index += 2) {
    bytes.push(Number.parseInt(value.slice(index, index + 2), 16))
  }
  return bytes
}

function walletProviderName(provider: SolanaWalletProvider): string {
  if (provider.isPhantom) return 'Phantom'
  if (provider.isSolflare) return 'Solflare'
  return 'Solana wallet'
}
