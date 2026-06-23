import { describe, expect, it } from 'vitest'
import { MARKET_SECTORS, sectorForSymbol } from '../marketSectors'

describe('marketSectors', () => {
  it('contains each symbol only once', () => {
    const symbols = MARKET_SECTORS.flatMap((sector) => sector.symbols)

    expect(new Set(symbols).size).toBe(symbols.length)
  })

  it('can find a sector for known VN30 symbols', () => {
    expect(sectorForSymbol('VCB')?.name).toBeTruthy()
    expect(sectorForSymbol('FPT')?.name).toBeTruthy()
  })
})
