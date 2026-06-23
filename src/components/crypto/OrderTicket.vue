<template>
  <form
    class="rounded-lg border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]"
    @submit.prevent="handleSubmit"
  >
    <div class="flex items-center justify-between gap-3">
      <div>
        <h2 class="text-lg font-semibold text-gray-900 dark:text-white">Order Ticket</h2>
        <p class="text-sm text-gray-500 dark:text-gray-400">{{ symbol }}</p>
      </div>
      <div class="inline-flex rounded-lg bg-gray-100 p-1 dark:bg-gray-900">
        <button
          type="button"
          class="rounded-md px-3 py-1.5 text-sm font-medium"
          :class="side === 'buy' ? 'bg-emerald-600 text-white' : 'text-gray-500 dark:text-gray-400'"
          @click="side = 'buy'"
        >
          Buy
        </button>
        <button
          type="button"
          class="rounded-md px-3 py-1.5 text-sm font-medium"
          :class="side === 'sell' ? 'bg-rose-600 text-white' : 'text-gray-500 dark:text-gray-400'"
          @click="side = 'sell'"
        >
          Sell
        </button>
      </div>
    </div>

    <label class="mt-5 block text-sm font-medium text-gray-700 dark:text-gray-300">
      Quantity
      <input
        v-model.number="quantity"
        type="number"
        min="0"
        step="0.000001"
        class="mt-2 h-11 w-full rounded-lg border border-gray-300 bg-transparent px-3 text-sm text-gray-900 outline-none focus:border-blue-500 dark:border-gray-700 dark:text-white"
      />
    </label>

    <dl class="mt-4 grid grid-cols-2 gap-3 text-sm">
      <div class="rounded-lg bg-gray-50 p-3 dark:bg-gray-900">
        <dt class="text-gray-500 dark:text-gray-400">Estimated notional</dt>
        <dd class="mt-1 font-semibold text-gray-900 dark:text-white">
          {{ formatCurrency(estimatedNotional) }}
        </dd>
      </div>
      <div class="rounded-lg bg-gray-50 p-3 dark:bg-gray-900">
        <dt class="text-gray-500 dark:text-gray-400">Fee</dt>
        <dd class="mt-1 font-semibold text-gray-900 dark:text-white">
          {{ formatCurrency(estimatedFee) }}
        </dd>
      </div>
    </dl>

    <p class="mt-3 text-xs text-gray-500 dark:text-gray-400">
      Simulated slippage estimate: {{ formatCurrency(estimatedSlippage) }}. Orders are virtual.
    </p>
    <p v-if="error" class="mt-3 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">
      {{ error }}
    </p>

    <button
      type="submit"
      class="mt-5 h-11 w-full rounded-lg bg-blue-600 text-sm font-semibold text-white hover:bg-blue-700"
    >
      Submit {{ side === 'buy' ? 'Buy' : 'Sell' }}
    </button>
  </form>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'

import type { CryptoSymbol, OrderSide } from '@/types/crypto'

const props = defineProps<{
  symbol: CryptoSymbol
  latestPrice: number
  error?: string
}>()

const emit = defineEmits<{
  submit: [order: { side: OrderSide; quantity: number }]
}>()

const side = ref<OrderSide>('buy')
const quantity = ref(0.1)
const estimatedNotional = computed(() => props.latestPrice * quantity.value)
const estimatedFee = computed(() => estimatedNotional.value * 0.001)
const estimatedSlippage = computed(() => estimatedNotional.value * 0.0005)

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 2,
  }).format(value)
}

function handleSubmit() {
  emit('submit', { side: side.value, quantity: quantity.value })
}
</script>
