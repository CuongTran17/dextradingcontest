export interface SectorDefinition {
  name: string
  symbols: string[]
}

export const MARKET_SECTORS: SectorDefinition[] = [
  { name: 'Banking', symbols: ['ACB', 'BID', 'CTG', 'MBB', 'SHB', 'SSB', 'STB', 'TCB', 'TPB', 'VCB', 'VIB', 'VPB'] },
  { name: 'Real Estate', symbols: ['BCM', 'VHM', 'VIC', 'VRE'] },
  { name: 'Energy', symbols: ['GAS', 'PLX', 'POW'] },
  { name: 'Industrial', symbols: ['GVR', 'HPG'] },
  { name: 'Consumer', symbols: ['MSN', 'MWG', 'SAB', 'VNM'] },
  { name: 'Transportation', symbols: ['VJC'] },
  { name: 'Insurance', symbols: ['BVH'] },
  { name: 'Securities', symbols: ['SSI'] },
  { name: 'Technology', symbols: ['FPT'] },
]

export function sectorForSymbol(symbol: string): SectorDefinition | undefined {
  const normalized = symbol.trim().toUpperCase()
  return MARKET_SECTORS.find((sector) => sector.symbols.includes(normalized))
}
