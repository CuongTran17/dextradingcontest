export type SymbolRegistryListener = (symbols: string[]) => void

function normalizeSymbols(symbols: Iterable<string>): string[] {
  return [...new Set(
    [...symbols]
      .map((symbol) => symbol.trim().toUpperCase())
      .filter((symbol) => /^[A-Z0-9]{2,10}$/.test(symbol)),
  )].sort()
}

export function createSymbolRegistry() {
  const symbolsByOwner = new Map<string, Set<string>>()
  const listeners = new Set<SymbolRegistryListener>()
  let activeSymbols: string[] = []

  function publishIfChanged(): void {
    const next = normalizeSymbols(
      [...symbolsByOwner.values()].flatMap((symbols) => [...symbols]),
    )
    if (next.join('|') === activeSymbols.join('|')) return
    activeSymbols = next
    listeners.forEach((listener) => listener([...activeSymbols]))
  }

  function replaceSymbols(ownerId: string, symbols: Iterable<string>): void {
    symbolsByOwner.set(ownerId, new Set(normalizeSymbols(symbols)))
    publishIfChanged()
  }

  function releaseOwner(ownerId: string): void {
    if (!symbolsByOwner.delete(ownerId)) return
    publishIfChanged()
  }

  function getReferenceCount(symbol: string): number {
    const normalized = symbol.trim().toUpperCase()
    return [...symbolsByOwner.values()].filter((symbols) => symbols.has(normalized)).length
  }

  function subscribe(listener: SymbolRegistryListener): () => void {
    listeners.add(listener)
    return () => listeners.delete(listener)
  }

  return {
    replaceSymbols,
    releaseOwner,
    getActiveSymbols: () => [...activeSymbols],
    getReferenceCount,
    subscribe,
  }
}

export const symbolRegistry = createSymbolRegistry()
