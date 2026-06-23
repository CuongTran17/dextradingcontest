import { describe, expect, it } from 'vitest'

import { calculatePortfolioMetrics, executeMarketOrder } from '@/services/tradingSimulator'
import type { VirtualPortfolio } from '@/types/crypto'

const emptyPortfolio: VirtualPortfolio = {
  contestId: 'practice-arena',
  cash: 10000,
  positions: [],
  orders: [],
}

describe('tradingSimulator', () => {
  it('executes a market buy and updates cash and position', () => {
    const portfolio = executeMarketOrder(emptyPortfolio, {
      contestId: 'practice-arena',
      symbol: 'BTCUSDT',
      side: 'buy',
      quantity: 0.1,
      latestPrice: 50000,
    })

    expect(portfolio.cash).toBeCloseTo(4995)
    expect(portfolio.positions[0]).toMatchObject({
      symbol: 'BTCUSDT',
      quantity: 0.1,
    })
    expect(portfolio.orders).toHaveLength(1)
  })

  it('rejects a sell order larger than the current position', () => {
    expect(() =>
      executeMarketOrder(emptyPortfolio, {
        contestId: 'practice-arena',
        symbol: 'BTCUSDT',
        side: 'sell',
        quantity: 0.1,
        latestPrice: 50000,
      }),
    ).toThrow('Insufficient BTCUSDT position')
  })

  it('calculates positive ROI when marked above entry', () => {
    const portfolio = executeMarketOrder(emptyPortfolio, {
      contestId: 'practice-arena',
      symbol: 'ETHUSDT',
      side: 'buy',
      quantity: 1,
      latestPrice: 3000,
    })

    const metrics = calculatePortfolioMetrics(portfolio, { ETHUSDT: 3300 })

    expect(metrics.roi).toBeGreaterThan(0)
    expect(metrics.pnl).toBeGreaterThan(0)
  })
})
