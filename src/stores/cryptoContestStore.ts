import type { VirtualPortfolio } from '@/types/crypto'

const STORAGE_KEY = 'crypto-contest-state-v1'

export interface CryptoContestState {
  joinedContestIds: string[]
  portfolios: Record<string, VirtualPortfolio>
}

const EMPTY_STATE: CryptoContestState = {
  joinedContestIds: [],
  portfolios: {},
}

export function createInitialPortfolio(
  contestId: string,
  initialCapital: number,
): VirtualPortfolio {
  return {
    contestId,
    cash: initialCapital,
    positions: [],
    orders: [],
  }
}

export function loadContestState(): CryptoContestState {
  const raw = window.localStorage.getItem(STORAGE_KEY)
  if (!raw) {
    return { ...EMPTY_STATE }
  }

  try {
    return JSON.parse(raw) as CryptoContestState
  } catch {
    return { ...EMPTY_STATE }
  }
}

export function saveContestState(state: CryptoContestState): void {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
}
