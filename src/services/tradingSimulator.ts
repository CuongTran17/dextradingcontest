import type { CryptoSymbol, OrderSide, Position, VirtualPortfolio } from '@/types/crypto'

const FEE_RATE = 0.001
const SLIPPAGE_RATE = 0.0005
const INITIAL_CAPITAL = 10000

interface MarketOrderInput {
  contestId: string
  symbol: CryptoSymbol
  side: OrderSide
  quantity: number
  latestPrice: number
}

interface PortfolioMetrics {
  cash: number
  positionsValue: number
  equity: number
  pnl: number
  roi: number
  volume: number
  tradeCount: number
}

function clonePositions(positions: Position[]): Position[] {
  return positions.map((position) => ({ ...position }))
}

export function executeMarketOrder(
  portfolio: VirtualPortfolio,
  input: MarketOrderInput,
): VirtualPortfolio {
  if (input.quantity <= 0) {
    throw new Error('Quantity must be greater than zero')
  }

  const executionPrice = input.latestPrice
  const notional = executionPrice * input.quantity
  const fee = notional * FEE_RATE
  const slippage = notional * SLIPPAGE_RATE
  const positions = clonePositions(portfolio.positions)
  let cash = portfolio.cash

  if (input.side === 'buy') {
    const totalCost = notional + fee
    if (cash < totalCost) {
      throw new Error('Insufficient USDT_TEST balance')
    }

    cash -= totalCost
    const existingPosition = positions.find((position) => position.symbol === input.symbol)
    if (existingPosition) {
      const previousNotional = existingPosition.quantity * existingPosition.averageEntry
      const nextQuantity = existingPosition.quantity + input.quantity
      existingPosition.quantity = nextQuantity
      existingPosition.averageEntry = (previousNotional + notional) / nextQuantity
    } else {
      positions.push({
        symbol: input.symbol,
        quantity: input.quantity,
        averageEntry: executionPrice,
      })
    }
  } else {
    const existingPosition = positions.find((position) => position.symbol === input.symbol)
    if (!existingPosition || existingPosition.quantity < input.quantity) {
      throw new Error(`Insufficient ${input.symbol} position`)
    }

    cash += notional - fee
    existingPosition.quantity -= input.quantity
  }

  const nextPositions = positions.filter((position) => position.quantity > 1e-12)

  return {
    ...portfolio,
    cash,
    positions: nextPositions,
    orders: [
      ...portfolio.orders,
      {
        id: `${input.contestId}-${Date.now()}-${portfolio.orders.length + 1}`,
        contestId: input.contestId,
        symbol: input.symbol,
        side: input.side,
        quantity: input.quantity,
        executionPrice,
        notional,
        fee,
        slippage,
        createdAt: new Date().toISOString(),
      },
    ],
  }
}

export function calculatePortfolioMetrics(
  portfolio: VirtualPortfolio,
  latestPrices: Partial<Record<CryptoSymbol, number>>,
): PortfolioMetrics {
  const positionsValue = portfolio.positions.reduce((total, position) => {
    return total + position.quantity * (latestPrices[position.symbol] ?? position.averageEntry)
  }, 0)
  const equity = portfolio.cash + positionsValue
  const pnl = equity - INITIAL_CAPITAL
  const volume = portfolio.orders.reduce((total, order) => total + order.notional, 0)

  return {
    cash: portfolio.cash,
    positionsValue,
    equity,
    pnl,
    roi: (pnl / INITIAL_CAPITAL) * 100,
    volume,
    tradeCount: portfolio.orders.length,
  }
}
