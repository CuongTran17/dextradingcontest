import { onUnmounted, watch, type WatchSource } from 'vue'
import { symbolRegistry } from '@/realtime/symbolRegistry'

export function usePriceSubscription(
  ownerId: string,
  symbols: WatchSource<Iterable<string>>,
): void {
  watch(
    symbols,
    (nextSymbols) => symbolRegistry.replaceSymbols(ownerId, nextSymbols),
    { immediate: true, deep: true },
  )

  onUnmounted(() => {
    symbolRegistry.releaseOwner(ownerId)
  })
}
