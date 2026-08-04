import {
  Connection,
  Keypair,
  PublicKey,
  SystemProgram,
  SYSVAR_RENT_PUBKEY,
  Transaction,
  TransactionInstruction,
} from '@solana/web3.js'
import { Buffer } from 'buffer'

const DEFAULT_SOLANA_RPC_URL = 'https://api.devnet.solana.com'
const MIN_JOIN_BALANCE_LAMPORTS = 5_000_000
const MAX_CONTEST_ID_LEN = 32
const MAX_BATCH_ID_LEN = 32
const INITIALIZE_CONTEST_DISCRIMINATOR = Uint8Array.from([8, 124, 233, 229, 42, 156, 92, 3])
const JOIN_CONTEST_DISCRIMINATOR = Uint8Array.from([247, 243, 77, 111, 247, 254, 100, 133])
const SET_JOIN_ENABLED_DISCRIMINATOR = Uint8Array.from([130, 14, 52, 92, 87, 2, 180, 137])
const PUBLISH_CERTIFICATE_ROOT_DISCRIMINATOR = Uint8Array.from([142, 166, 41, 131, 130, 127, 48, 25])
const CLAIM_CERTIFICATE_DISCRIMINATOR = Uint8Array.from([45, 124, 106, 139, 156, 89, 153, 233])
const TOKEN_PROGRAM_ID = new PublicKey('TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA')
const ASSOCIATED_TOKEN_PROGRAM_ID = new PublicKey('ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL')
const TOKEN_METADATA_PROGRAM_ID = new PublicKey('metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s')
const textEncoder = new TextEncoder()

interface SolanaWalletProvider {
  isPhantom?: boolean
  isSolflare?: boolean
  publicKey?: PublicKey
  connect: (options?: { onlyIfTrusted?: boolean }) => Promise<{ publicKey: PublicKey }>
  disconnect?: () => Promise<void>
  signAndSendTransaction?: (transaction: Transaction) => Promise<{ signature: string }>
  signTransaction?: (transaction: Transaction) => Promise<Transaction>
}

export interface SolanaWalletSigner {
  publicKey: PublicKey
  walletName: string
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
  batchId: string
  topN: number
  walletPublicKey: string
  rank: number
  metadataUri: string
  snapshotHash: string
  proof: string[]
}

export interface ClaimCertificateOnchainResult {
  signature: string
  mintAddress: string
}

export interface ConnectSolanaWalletResult {
  walletAddress: string
  walletName: string
}

export interface InitializeContestOnchainInput {
  contestId: string
}

export interface InitializeContestOnchainResult {
  adminWallet: string
  contestAddress: string
  signature: string
}

export interface SetContestJoinEnabledOnchainInput {
  contestId: string
  enabled: boolean
  contestAddress?: string | null
  expectedAdminWallet?: string
}

export interface SetContestJoinEnabledOnchainResult {
  adminWallet: string
  contestAddress: string
  signature: string
}

export interface PublishCertificateRootOnchainInput {
  contestId: string
  contestAddress?: string | null
  rootHex: string
  snapshotHashHex: string
  topN: number
  batchId: string
  expectedAdminWallet?: string
}

export interface PublishCertificateRootOnchainResult {
  adminWallet: string
  contestAddress: string
  signature: string
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

function walletSignerFromProvider(provider: SolanaWalletProvider): SolanaWalletSigner {
  const publicKey = provider.publicKey
  if (!publicKey) {
    throw new Error('Connect a Solana wallet before signing transactions')
  }
  return {
    publicKey,
    walletName: walletProviderName(provider),
    signAndSendTransaction: provider.signAndSendTransaction?.bind(provider),
    signTransaction: provider.signTransaction?.bind(provider),
  }
}

async function resolveSolanaSigner(explicitSigner?: SolanaWalletSigner): Promise<SolanaWalletSigner> {
  if (explicitSigner) return explicitSigner
  const provider = solanaProvider()
  const connected = await provider.connect()
  return {
    ...walletSignerFromProvider({ ...provider, publicKey: connected.publicKey }),
    publicKey: connected.publicKey,
  }
}

export async function connectSolanaWallet(): Promise<ConnectSolanaWalletResult> {
  const provider = solanaProvider()
  const connected = await provider.connect({ onlyIfTrusted: false })
  return {
    walletAddress: connected.publicKey.toBase58(),
    walletName: walletProviderName(provider),
  }
}

export async function disconnectSolanaWallet(): Promise<void> {
  const provider = window.solana
  if (provider?.disconnect) {
    await provider.disconnect()
  }
}

export async function initializeContestOnchain(
  input: InitializeContestOnchainInput,
  signer?: SolanaWalletSigner,
): Promise<InitializeContestOnchainResult> {
  if (Buffer.byteLength(input.contestId, 'utf8') > 32) {
    throw new Error('Contest id must be 32 bytes or shorter for Solana')
  }

  const activeSigner = await resolveSolanaSigner(signer)
  const admin = activeSigner.publicKey
  const programId = contestProgramId()
  const contest = PublicKey.findProgramAddressSync(
    [textEncoder.encode('contest'), textEncoder.encode(input.contestId)],
    programId,
  )[0]
  const connection = new Connection(solanaRpcUrl(), 'confirmed')
  const existingContest = await connection.getAccountInfo(contest, 'confirmed')
  if (existingContest) {
    throw new Error(`Contest ${input.contestId} is already initialized on Solana devnet`)
  }

  const balance = await connection.getBalance(admin, 'confirmed')
  if (balance < MIN_JOIN_BALANCE_LAMPORTS) {
    throw new Error('Admin Solana devnet wallet needs SOL before initializing this contest')
  }

  const transaction = new Transaction().add(
    new TransactionInstruction({
      programId,
      keys: [
        { pubkey: contest, isSigner: false, isWritable: true },
        { pubkey: admin, isSigner: true, isWritable: true },
        { pubkey: SystemProgram.programId, isSigner: false, isWritable: false },
      ],
      data: Buffer.concat([
        Buffer.from(INITIALIZE_CONTEST_DISCRIMINATOR),
        encodeAnchorString(input.contestId),
      ]),
    }),
  )
  transaction.feePayer = admin
  transaction.recentBlockhash = (await connection.getLatestBlockhash()).blockhash

  const { signature } = await signAndConfirm(activeSigner, connection, transaction)
  return {
    adminWallet: admin.toBase58(),
    contestAddress: contest.toBase58(),
    signature,
  }
}

export async function setContestJoinEnabledOnchain(
  input: SetContestJoinEnabledOnchainInput,
  signer?: SolanaWalletSigner,
): Promise<SetContestJoinEnabledOnchainResult> {
  if (Buffer.byteLength(input.contestId, 'utf8') > 32) {
    throw new Error('Contest id must be 32 bytes or shorter for Solana')
  }

  const activeSigner = await resolveSolanaSigner(signer)
  const admin = activeSigner.publicKey
  if (input.expectedAdminWallet && admin.toBase58() !== input.expectedAdminWallet) {
    throw new Error('Connected wallet is not the admin wallet that initialized this contest')
  }

  const programId = contestProgramId()
  const connection = new Connection(solanaRpcUrl(), 'confirmed')
  const contest = await resolveContestAccountAddress(
    connection,
    input.contestId,
    programId,
    input.contestAddress,
  )
  const contestAccount = await connection.getAccountInfo(contest, 'confirmed')
  if (!contestAccount) {
    throw new Error(`Contest ${input.contestId} is not initialized on Solana devnet`)
  }

  const transaction = new Transaction().add(
    new TransactionInstruction({
      programId,
      keys: [
        { pubkey: contest, isSigner: false, isWritable: true },
        { pubkey: admin, isSigner: true, isWritable: false },
      ],
      data: Buffer.concat([
        Buffer.from(SET_JOIN_ENABLED_DISCRIMINATOR),
        Buffer.from([input.enabled ? 1 : 0]),
      ]),
    }),
  )
  transaction.feePayer = admin
  transaction.recentBlockhash = (await connection.getLatestBlockhash()).blockhash

  const { signature } = await signAndConfirm(activeSigner, connection, transaction, {
    preferSeparateSignAndSend: true,
  })
  return {
    adminWallet: admin.toBase58(),
    contestAddress: contest.toBase58(),
    signature,
  }
}

export async function publishCertificateRootOnchain(
  input: PublishCertificateRootOnchainInput,
  signer?: SolanaWalletSigner,
): Promise<PublishCertificateRootOnchainResult> {
  if (Buffer.byteLength(input.contestId, 'utf8') > 32) {
    throw new Error('Contest id must be 32 bytes or shorter for Solana')
  }
  if (!Number.isInteger(input.topN) || input.topN < 1 || input.topN > 100) {
    throw new Error('Certificate topN must be between 1 and 100')
  }

  const root = hexToBytes32(input.rootHex, 'Certificate root')
  const snapshotHash = hexToBytes32(input.snapshotHashHex, 'Snapshot hash')
  const activeSigner = await resolveSolanaSigner(signer)
  const admin = activeSigner.publicKey
  if (input.expectedAdminWallet && admin.toBase58() !== input.expectedAdminWallet) {
    throw new Error('Connected wallet is not the admin wallet that initialized this contest')
  }

  const programId = contestProgramId()
  const connection = new Connection(solanaRpcUrl(), 'confirmed')
  const contest = await resolveContestAccountAddress(
    connection,
    input.contestId,
    programId,
    input.contestAddress,
  )
  const contestAccount = await connection.getAccountInfo(contest, 'confirmed')
  if (!contestAccount) {
    throw new Error(`Contest ${input.contestId} is not initialized on Solana devnet`)
  }

  const transaction = new Transaction().add(
    new TransactionInstruction({
      programId,
      keys: [
        { pubkey: contest, isSigner: false, isWritable: true },
        { pubkey: admin, isSigner: true, isWritable: false },
      ],
      data: encodePublishCertificateRootInstruction({
        root,
        snapshotHash,
        topN: input.topN,
        batchId: input.batchId,
      }),
    }),
  )
  transaction.feePayer = admin
  transaction.recentBlockhash = (await connection.getLatestBlockhash()).blockhash

  const { signature } = await signAndConfirm(activeSigner, connection, transaction)
  return {
    adminWallet: admin.toBase58(),
    contestAddress: contest.toBase58(),
    signature,
  }
}

export async function joinContestOnchain(
  input: JoinContestOnchainInput,
  signer?: SolanaWalletSigner,
): Promise<JoinContestOnchainResult> {
  const activeSigner = await resolveSolanaSigner(signer)
  const wallet = activeSigner.publicKey
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
  const existingParticipant = await connection.getAccountInfo(participant, 'confirmed')
  if (existingParticipant) {
    const signature = await latestSignatureForAddress(connection, participant)
    if (!signature) {
      throw new Error(
        'This wallet already joined on Solana, but no transaction signature was found to sync with the backend',
      )
    }
    return { walletAddress: wallet.toBase58(), signature }
  }

  await assertJoinPrerequisites(connection, input.contestId, contest, wallet)
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

  const { signature } = await signAndConfirm(activeSigner, connection, transaction)
  return { walletAddress: wallet.toBase58(), signature }
}

async function latestSignatureForAddress(
  connection: Connection,
  address: PublicKey,
): Promise<string | null> {
  const signatures = await connection.getSignaturesForAddress(address, { limit: 1 })
  return signatures[0]?.signature ?? null
}

async function assertJoinPrerequisites(
  connection: Connection,
  contestId: string,
  contest: PublicKey,
  wallet: PublicKey,
): Promise<void> {
  const contestAccount = await connection.getAccountInfo(contest, 'confirmed')
  if (!contestAccount) {
    throw new Error(
      `Contest ${contestId} is not initialized on Solana devnet. Ask an admin to run initialize-contest for this contest id.`,
    )
  }

  const balance = await connection.getBalance(wallet, 'confirmed')
  if (balance < MIN_JOIN_BALANCE_LAMPORTS) {
    throw new Error('Your Solana devnet wallet needs SOL before joining this contest')
  }
}

export async function claimCertificateOnchain(
  input: ClaimCertificateOnchainInput,
  signer?: SolanaWalletSigner,
): Promise<ClaimCertificateOnchainResult> {
  const snapshotHash = hexToBytes32(input.snapshotHash, 'Snapshot hash')
  const proof = input.proof.map((item) => hexToBytes32(item, 'Merkle proof item'))
  if (!Number.isInteger(input.rank) || input.rank < 0 || input.rank > 255) {
    throw new Error('Certificate rank must fit in one byte')
  }
  if (!Number.isInteger(input.topN) || input.topN < 1 || input.topN > 100) {
    throw new Error('Certificate topN must be between 1 and 100')
  }

  const activeSigner = await resolveSolanaSigner(signer)
  const wallet = activeSigner.publicKey
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
  const mint = Keypair.generate()
  const tokenAccount = PublicKey.findProgramAddressSync(
    [wallet.toBuffer(), TOKEN_PROGRAM_ID.toBuffer(), mint.publicKey.toBuffer()],
    ASSOCIATED_TOKEN_PROGRAM_ID,
  )[0]
  const metadata = PublicKey.findProgramAddressSync(
    [
      textEncoder.encode('metadata'),
      TOKEN_METADATA_PROGRAM_ID.toBuffer(),
      mint.publicKey.toBuffer(),
    ],
    TOKEN_METADATA_PROGRAM_ID,
  )[0]
  const data = encodeClaimCertificateInstruction({
    contestId: input.contestId,
    batchId: input.batchId,
    topN: input.topN,
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
        { pubkey: mint.publicKey, isSigner: true, isWritable: true },
        { pubkey: tokenAccount, isSigner: false, isWritable: true },
        { pubkey: metadata, isSigner: false, isWritable: true },
        { pubkey: wallet, isSigner: true, isWritable: true },
        { pubkey: TOKEN_PROGRAM_ID, isSigner: false, isWritable: false },
        { pubkey: ASSOCIATED_TOKEN_PROGRAM_ID, isSigner: false, isWritable: false },
        { pubkey: TOKEN_METADATA_PROGRAM_ID, isSigner: false, isWritable: false },
        { pubkey: SystemProgram.programId, isSigner: false, isWritable: false },
        { pubkey: SYSVAR_RENT_PUBKEY, isSigner: false, isWritable: false },
      ],
      data,
    }),
  )
  transaction.feePayer = wallet
  transaction.recentBlockhash = (await connection.getLatestBlockhash()).blockhash
  transaction.partialSign(mint)

  await assertTransactionSimulation(connection, transaction)
  const { signature } = await signAndConfirm(activeSigner, connection, transaction, {
    preferSeparateSignAndSend: true,
  })
  return { signature, mintAddress: mint.publicKey.toBase58() }
}

async function assertTransactionSimulation(
  connection: Connection,
  transaction: Transaction,
): Promise<void> {
  const simulation = await connection.simulateTransaction(transaction, undefined, false)
  if (simulation.value.err) {
    throw new Error(formatSimulationError(simulation.value.logs ?? [], simulation.value.err))
  }
}

function formatSimulationError(logs: string[], err: unknown): string {
  const anchorError = logs
    .map((line) => line.match(/Error Message:\s*(.+?)(?:\.)?$/)?.[1])
    .find(Boolean)
  if (anchorError) return anchorError

  const usefulLog = [...logs]
    .reverse()
    .find((line) => /insufficient|error|failed|custom program error/i.test(line))
  if (usefulLog) return usefulLog.replace(/^Program log:\s*/, '')

  return `Solana preflight failed: ${JSON.stringify(err)}`
}

async function signAndConfirm(
  signer: SolanaWalletSigner,
  connection: Connection,
  transaction: Transaction,
  options: { preferSeparateSignAndSend?: boolean } = {},
): Promise<{ signature: string }> {
  if (signer.signAndSendTransaction && !options.preferSeparateSignAndSend) {
    const { signature } = await signer.signAndSendTransaction(transaction).catch((error: unknown) => {
      throw normalizeSolanaWalletError(error)
    })
    await connection.confirmTransaction(signature, 'confirmed').catch(() => undefined)
    return { signature }
  }

  if (!signer.signTransaction) {
    throw new Error('Connected wallet cannot sign Solana transactions')
  }
  const signed = await signer.signTransaction(transaction).catch((error: unknown) => {
    throw normalizeSolanaWalletError(error)
  })
  const signature = await connection.sendRawTransaction(signed.serialize()).catch((error: unknown) => {
    throw normalizeSolanaWalletError(error)
  })
  await connection.confirmTransaction(signature, 'confirmed').catch(() => undefined)
  return { signature }
}

export function normalizeSolanaWalletError(error: unknown): Error {
  if (error instanceof Error && /reject|decline|denied|cancel/i.test(error.message)) {
    return new Error('Wallet request was rejected')
  }
  const logs = extractSolanaLogs(error)
  if (logs.length > 0) {
    const message = formatSimulationError(logs, error)
    if (message && message !== 'Unexpected error') return new Error(message)
  }

  if (error instanceof Error && error.message) {
    return error
  }
  return new Error(String(error || 'Solana wallet transaction failed'))
}

function extractSolanaLogs(error: unknown): string[] {
  const candidates: unknown[] = [error]
  if (error && typeof error === 'object') {
    const record = error as Record<string, unknown>
    candidates.push(record.data, record.error)
    if (record.data && typeof record.data === 'object') {
      candidates.push((record.data as Record<string, unknown>).data)
    }
    if (record.error && typeof record.error === 'object') {
      candidates.push((record.error as Record<string, unknown>).data)
    }
  }

  for (const candidate of candidates) {
    if (!candidate || typeof candidate !== 'object') continue
    const logs = (candidate as Record<string, unknown>).logs
    if (Array.isArray(logs)) {
      return logs.filter((item): item is string => typeof item === 'string')
    }
  }
  return []
}

function encodeClaimCertificateInstruction(input: {
  contestId: string
  batchId: string
  topN: number
  rank: number
  metadataUri: string
  snapshotHash: number[]
  proof: number[][]
}): Buffer {
  const topN = Buffer.alloc(2)
  topN.writeUInt16LE(input.topN, 0)
  return Buffer.concat([
    Buffer.from(CLAIM_CERTIFICATE_DISCRIMINATOR),
    encodeAnchorString(input.contestId),
    encodeAnchorString(input.batchId),
    topN,
    Buffer.from([input.rank]),
    encodeAnchorString(input.metadataUri),
    Buffer.from(input.snapshotHash),
    encodeAnchorVec32(input.proof),
  ])
}

function contestAccountAddress(
  contestId: string,
  programId: PublicKey,
  storedAddress?: string | null,
): PublicKey {
  if (storedAddress) {
    return new PublicKey(storedAddress)
  }
  return PublicKey.findProgramAddressSync(
    [textEncoder.encode('contest'), textEncoder.encode(contestId)],
    programId,
  )[0]
}

async function resolveContestAccountAddress(
  connection: Connection,
  contestId: string,
  programId: PublicKey,
  storedAddress?: string | null,
): Promise<PublicKey> {
  const contest = contestAccountAddress(contestId, programId, storedAddress)
  if (!storedAddress) return contest

  const account = await connection.getAccountInfo(contest, 'confirmed')
  if (!account) {
    throw new Error(`Stored Solana contest address ${contest.toBase58()} is not initialized on devnet`)
  }
  if (!account.owner.equals(programId)) {
    throw new Error(`Stored Solana contest address ${contest.toBase58()} is not owned by the contest program`)
  }

  const decoded = decodeContestAccountState(Buffer.from(account.data))
  if (!decoded) {
    throw new Error(`Stored Solana contest address ${contest.toBase58()} is not a contest account`)
  }
  if (decoded.contestId !== contestId) {
    throw new Error(
      `Stored Solana contest address belongs to on-chain contest ${decoded.contestId}, but this contest is ${contestId}`,
    )
  }

  const expectedContest = contestAccountAddress(decoded.contestId, programId)
  if (!expectedContest.equals(contest)) {
    throw new Error(
      `Stored Solana contest address ${contest.toBase58()} does not match the PDA for on-chain contest ${decoded.contestId}`,
    )
  }
  return contest
}

function decodeContestAccountState(data: Buffer): { contestId: string; bump: number } | null {
  let offset = 8
  if (data.length < offset + 32 + 4) return null

  offset += 32
  const contestIdLength = data.readUInt32LE(offset)
  offset += 4
  if (contestIdLength > MAX_CONTEST_ID_LEN || data.length < offset + contestIdLength) return null
  const contestId = data.subarray(offset, offset + contestIdLength).toString('utf8')
  offset += contestIdLength

  offset += 1 + 32 + 32 + 2
  if (data.length < offset + 4) return null
  const batchIdLength = data.readUInt32LE(offset)
  offset += 4 + batchIdLength
  if (batchIdLength > MAX_BATCH_ID_LEN || data.length < offset + 1) return null

  return {
    contestId,
    bump: data[offset],
  }
}

function encodePublishCertificateRootInstruction(input: {
  root: number[]
  snapshotHash: number[]
  topN: number
  batchId: string
}): Buffer {
  const topN = Buffer.alloc(2)
  topN.writeUInt16LE(input.topN, 0)
  return Buffer.concat([
    Buffer.from(PUBLISH_CERTIFICATE_ROOT_DISCRIMINATOR),
    Buffer.from(input.root),
    Buffer.from(input.snapshotHash),
    topN,
    encodeAnchorString(input.batchId),
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
