import type { Contest } from '@/types/crypto'

export const DEFAULT_CONTEST_ID = 'practice-arena'

export const CRYPTO_CONTESTS: Contest[] = [
  {
    id: 'practice-arena',
    title: 'Practice Arena',
    status: 'practice',
    mode: 'practice',
    initialCapital: 10000,
    symbols: ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'XRPUSDT', 'BNBUSDT'],
    startsAt: '2026-06-23T00:00:00.000Z',
    endsAt: '2026-12-31T23:59:59.000Z',
    participantCount: 128,
  },
  {
    id: 'summer-crypto-cup',
    title: 'Summer Crypto Cup',
    status: 'active',
    mode: 'contest',
    initialCapital: 10000,
    symbols: ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'XRPUSDT', 'BNBUSDT'],
    startsAt: '2026-06-20T00:00:00.000Z',
    endsAt: '2026-07-20T23:59:59.000Z',
    participantCount: 42,
  },
]
