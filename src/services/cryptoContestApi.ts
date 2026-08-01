import { getToken } from '@/services/authApi'
import { backendFetch, normalizeBackendUrl } from '@/services/httpClient'
import type {
  AdminContestParticipant,
  Contest,
  ContestCreateInput,
  ContestUpdateInput,
  LeaderboardRow,
  LeaderboardSortBy,
  ParticipantStatus,
} from '@/types/crypto'

const BACKEND_URL = normalizeBackendUrl(import.meta.env.VITE_BACKEND_URL)

interface BackendContest {
  id: Contest['id']
  title: string
  status: Contest['status']
  raw_status: string
  mode: Contest['mode']
  initial_capital: number
  quote_asset: string
  symbols: Contest['symbols']
  starts_at: string | null
  ends_at: string | null
  participant_count: number
  onchain_contest_address?: string | null
  onchain_initialize_tx_signature?: string | null
  onchain_admin_wallet?: string | null
  onchain_initialized_at?: string | null
}

interface BackendLeaderboardRow {
  rank: number
  user: string
  equity: number
  pnl: number
  roi: number
  volume: number
  trade_count: number
  last_trade: string | null
}

interface BackendAdminContestParticipant {
  user_id: number
  user: string
  status: ParticipantStatus
  account_status: AdminContestParticipant['accountStatus']
  equity: number
  pnl: number
  roi: number
  volume: number
  trade_count: number
  last_trade: string | null
}

export interface CertificateExportResult {
  batch_id: string
  contest_id: string
  top_n: number
  snapshot_hash: string
  merkle_root: string
  claims: Array<{
    participant_id: number
    wallet_address: string
    rank: number
    recipient_name: string
    image_uri: string
    metadata_uri: string
    merkle_leaf: string
    proof: string[]
  }>
}

export interface CertificateBatchAuthorizationResult {
  batch_id: string
  contest_id: string
  top_n: number
  snapshot_hash: string
  merkle_root: string
  status: string
  authorized_by_wallet: string | null
  authorize_tx_signature: string | null
  authorized_at: string | null
}

export interface ContestSettlementResult {
  status: string
  contest_id: string
  version: number
  snapshot_hash: string
  settlement_prices: Record<string, { price: number; time: number }>
  rows: Array<Record<string, unknown>>
  cancelled_orders: Array<Record<string, unknown>>
  settled_at: string
}

function adminHeaders(): HeadersInit {
  const token = getToken()
  if (!token) throw new Error('Please sign in as admin')
  return { Authorization: `Bearer ${token}` }
}

export async function fetchContests(): Promise<Contest[]> {
  const contests = await backendFetch<BackendContest[]>(
    BACKEND_URL,
    '/api/crypto/contests',
  )
  return contests.map(mapContest)
}

export async function fetchContest(contestId: string): Promise<Contest> {
  const contest = await backendFetch<BackendContest>(
    BACKEND_URL,
    `/api/crypto/contests/${encodeURIComponent(contestId)}`,
  )
  return mapContest(contest)
}

export async function fetchContestLeaderboard(contestId: string, refresh = false): Promise<LeaderboardRow[]> {
  const query = refresh ? '?refresh=true' : ''
  const rows = await backendFetch<BackendLeaderboardRow[]>(
    BACKEND_URL,
    `/api/crypto/contests/${encodeURIComponent(contestId)}/leaderboard${query}`,
  )
  return rows.map((row) => ({
    rank: row.rank,
    user: row.user,
    equity: row.equity,
    pnl: row.pnl,
    roi: row.roi,
    volume: row.volume,
    tradeCount: row.trade_count,
    lastTrade: row.last_trade,
  }))
}

export async function fetchLeaderboardSnapshot(
  contestId: string,
  sortBy?: LeaderboardSortBy,
): Promise<LeaderboardRow[]> {
  const query = sortBy ? `?sort_by=${encodeURIComponent(sortBy)}` : ''
  const response = await backendFetch<{
    contest_id: string
    sort_by: string
    updated_at: string
    rows: BackendLeaderboardRow[]
  }>(BACKEND_URL, `/api/leaderboard/${encodeURIComponent(contestId)}${query}`)
  return response.rows.map((row) => ({
    rank: row.rank,
    user: row.user,
    equity: row.equity,
    pnl: row.pnl,
    roi: row.roi,
    volume: row.volume,
    tradeCount: row.trade_count,
    lastTrade: row.last_trade,
  }))
}

export async function createAdminCryptoContest(input: ContestCreateInput): Promise<Contest> {
  const contest = await backendFetch<BackendContest>(
    BACKEND_URL,
    '/api/admin/crypto/contests',
    {
      method: 'POST',
      headers: adminHeaders(),
      body: JSON.stringify({
        slug: input.slug,
        title: input.title,
        mode: input.mode,
        status: input.status,
        initial_balance: input.initialBalance,
        symbols: input.symbols,
        starts_at: input.startsAt ?? null,
        ends_at: input.endsAt ?? null,
      }),
    },
  )
  return mapContest(contest)
}

export async function updateAdminCryptoContest(
  contestId: string,
  input: ContestUpdateInput,
): Promise<Contest> {
  const contest = await backendFetch<BackendContest>(
    BACKEND_URL,
    `/api/admin/crypto/contests/${encodeURIComponent(contestId)}`,
    {
      method: 'PUT',
      headers: adminHeaders(),
      body: JSON.stringify({
        title: input.title,
        status: input.status,
        symbols: input.symbols,
        starts_at: input.startsAt,
        ends_at: input.endsAt,
      }),
    },
  )
  return mapContest(contest)
}

export async function fetchAdminCryptoContests(): Promise<Contest[]> {
  const contests = await backendFetch<BackendContest[]>(
    BACKEND_URL,
    '/api/admin/crypto/contests',
    {
      headers: adminHeaders(),
    },
  )
  return contests.map(mapContest)
}

export async function setAdminCryptoContestStatus(
  contestId: string,
  status: string,
): Promise<Contest> {
  const contest = await backendFetch<BackendContest>(
    BACKEND_URL,
    `/api/admin/crypto/contests/${encodeURIComponent(contestId)}/status?status=${encodeURIComponent(status)}`,
    {
      method: 'PUT',
      headers: adminHeaders(),
    },
  )
  return mapContest(contest)
}

export async function confirmContestOnchainInitialize(input: {
  contestId: string
  contestAddress: string
  initializeTxSignature: string
  adminWallet: string
}): Promise<Contest> {
  const contest = await backendFetch<BackendContest>(
    BACKEND_URL,
    `/api/admin/crypto/contests/${encodeURIComponent(input.contestId)}/onchain/confirm`,
    {
      method: 'POST',
      headers: adminHeaders(),
      body: JSON.stringify({
        contest_address: input.contestAddress,
        initialize_tx_signature: input.initializeTxSignature,
        admin_wallet: input.adminWallet,
      }),
    },
  )
  return mapContest(contest)
}

export async function fetchAdminContestParticipants(
  contestId: string,
): Promise<AdminContestParticipant[]> {
  const participants = await backendFetch<BackendAdminContestParticipant[]>(
    BACKEND_URL,
    `/api/admin/crypto/contests/${encodeURIComponent(contestId)}/participants`,
    {
      headers: adminHeaders(),
    },
  )
  return participants.map(mapAdminContestParticipant)
}

export async function setAdminContestParticipantStatus(
  contestId: string,
  userId: number,
  status: ParticipantStatus,
): Promise<AdminContestParticipant> {
  const participant = await backendFetch<BackendAdminContestParticipant>(
    BACKEND_URL,
    `/api/admin/crypto/contests/${encodeURIComponent(contestId)}/participants/${userId}/status?status=${encodeURIComponent(status)}`,
    {
      method: 'PUT',
      headers: adminHeaders(),
    },
  )
  return mapAdminContestParticipant(participant)
}

export async function exportContestCertificates(
  contestId: string,
  options: { topN?: number } = {},
): Promise<CertificateExportResult> {
  return backendFetch<CertificateExportResult>(
    BACKEND_URL,
    `/api/admin/crypto/contests/${encodeURIComponent(contestId)}/certificates/export`,
    {
      method: 'POST',
      headers: adminHeaders(),
      body: JSON.stringify({ top_n: options.topN ?? 10 }),
    },
  )
}

export async function confirmCertificateBatchAuthorization(input: {
  contestId: string
  batchId: string
  adminWallet: string
  authorizeTxSignature: string
}): Promise<CertificateBatchAuthorizationResult> {
  return backendFetch<CertificateBatchAuthorizationResult>(
    BACKEND_URL,
    `/api/admin/crypto/contests/${encodeURIComponent(input.contestId)}/certificates/batches/${encodeURIComponent(input.batchId)}/authorize/confirm`,
    {
      method: 'POST',
      headers: adminHeaders(),
      body: JSON.stringify({
        admin_wallet: input.adminWallet,
        authorize_tx_signature: input.authorizeTxSignature,
      }),
    },
  )
}

export async function settleAdminCryptoContest(
  contestId: string,
): Promise<ContestSettlementResult> {
  return backendFetch<ContestSettlementResult>(
    BACKEND_URL,
    `/api/admin/crypto/contests/${encodeURIComponent(contestId)}/settle`,
    {
      method: 'POST',
      headers: adminHeaders(),
    },
  )
}

function mapContest(contest: BackendContest): Contest {
  return {
    id: contest.id,
    title: contest.title,
    status: contest.status,
    rawStatus: contest.raw_status as Contest['rawStatus'],
    mode: contest.mode,
    initialCapital: contest.initial_capital,
    symbols: contest.symbols,
    startsAt: contest.starts_at ?? '',
    endsAt: contest.ends_at ?? '',
    participantCount: contest.participant_count,
    onchainContestAddress: contest.onchain_contest_address ?? null,
    onchainInitializeTxSignature: contest.onchain_initialize_tx_signature ?? null,
    onchainAdminWallet: contest.onchain_admin_wallet ?? null,
    onchainInitializedAt: contest.onchain_initialized_at ?? null,
  }
}

function mapAdminContestParticipant(
  participant: BackendAdminContestParticipant,
): AdminContestParticipant {
  return {
    userId: participant.user_id,
    user: participant.user,
    status: participant.status,
    accountStatus: participant.account_status,
    equity: participant.equity,
    pnl: participant.pnl,
    roi: participant.roi,
    volume: participant.volume,
    tradeCount: participant.trade_count,
    lastTrade: participant.last_trade,
  }
}
