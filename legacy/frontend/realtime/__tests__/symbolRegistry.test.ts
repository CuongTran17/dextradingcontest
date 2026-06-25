import { describe, expect, it, vi } from 'vitest'
import { createSymbolRegistry } from '@/realtime/symbolRegistry'

describe('symbolRegistry', () => {
  it('keeps a symbol active while at least one owner retains it', () => {
    const registry = createSymbolRegistry()

    registry.replaceSymbols('dashboard', ['fpt', 'VCB'])
    registry.replaceSymbols('portfolio', ['FPT'])
    registry.releaseOwner('dashboard')

    expect(registry.getActiveSymbols()).toEqual(['FPT'])
    expect(registry.getReferenceCount('FPT')).toBe(1)
  })

  it('notifies only when the active symbol set changes', () => {
    const registry = createSymbolRegistry()
    const listener = vi.fn()
    registry.subscribe(listener)

    registry.replaceSymbols('dashboard', ['FPT', 'FPT'])
    registry.replaceSymbols('dashboard', ['FPT'])
    registry.releaseOwner('dashboard')

    expect(listener).toHaveBeenCalledTimes(2)
    expect(listener).toHaveBeenLastCalledWith([])
  })
})
