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

    <!-- Order Type Selector: Market vs Limit -->
    <div class="mt-4 flex rounded-lg bg-gray-100 p-1 dark:bg-gray-900">
      <button
        type="button"
        class="flex-1 rounded-md py-1.5 text-xs font-semibold uppercase tracking-wider transition-all"
        :class="orderType === 'market' ? 'bg-white text-gray-900 shadow-sm dark:bg-gray-800 dark:text-white' : 'text-gray-500 dark:text-gray-400'"
        @click="orderType = 'market'"
      >
        Market
      </button>
      <button
        type="button"
        class="flex-1 rounded-md py-1.5 text-xs font-semibold uppercase tracking-wider transition-all"
        :class="orderType === 'limit' ? 'bg-white text-gray-900 shadow-sm dark:bg-gray-800 dark:text-white' : 'text-gray-500 dark:text-gray-400'"
        @click="orderType = 'limit'"
      >
        Limit
      </button>
    </div>

    <!-- Quantity Field -->
    <label class="mt-4 block text-sm font-medium text-gray-700 dark:text-gray-300">
      Quantity
      <input
        v-model.number="quantity"
        type="number"
        min="0"
        step="0.000001"
        class="mt-1 h-10 w-full rounded-lg border border-gray-300 bg-transparent px-3 text-sm text-gray-900 outline-none focus:border-blue-500 dark:border-gray-700 dark:text-white"
      />
    </label>

    <!-- Limit Price Field (when Limit order selected) -->
    <label v-if="orderType === 'limit'" class="mt-3 block text-sm font-medium text-gray-700 dark:text-gray-300">
      Limit Price ($)
      <input
        v-model.number="limitPrice"
        type="number"
        min="0"
        step="0.01"
        class="mt-1 h-10 w-full rounded-lg border border-gray-300 bg-transparent px-3 text-sm text-gray-900 outline-none focus:border-blue-500 dark:border-gray-700 dark:text-white"
        :placeholder="`Current: ${latestPrice}`"
      />
    </label>

    <!-- TP/SL Expandable Toggle -->
    <div class="mt-3">
      <button
        type="button"
        class="text-xs font-medium text-blue-600 hover:underline dark:text-blue-400"
        @click="showTpSl = !showTpSl"
      >
        {{ showTpSl ? '− Hide TP / SL' : '+ Add Take-Profit / Stop-Loss' }}
      </button>
      <div v-if="showTpSl" class="mt-2 grid grid-cols-2 gap-3">
        <label class="block text-xs font-medium text-gray-600 dark:text-gray-400">
          Take Profit ($)
          <input
            v-model.number="takeProfitPrice"
            type="number"
            min="0"
            step="0.01"
            class="mt-1 h-9 w-full rounded-md border border-gray-300 bg-transparent px-2 text-xs text-gray-900 outline-none focus:border-emerald-500 dark:border-gray-700 dark:text-white"
            placeholder="TP price"
          />
        </label>
        <label class="block text-xs font-medium text-gray-600 dark:text-gray-400">
          Stop Loss ($)
          <input
            v-model.number="stopLossPrice"
            type="number"
            min="0"
            step="0.01"
            class="mt-1 h-9 w-full rounded-md border border-gray-300 bg-transparent px-2 text-xs text-gray-900 outline-none focus:border-rose-500 dark:border-gray-700 dark:text-white"
            placeholder="SL price"
          />
        </label>
      </div>
    </div>

    <dl class="mt-4 grid grid-cols-2 gap-3 text-sm">
      <div class="rounded-lg bg-gray-50 p-3 dark:bg-gray-900">
        <dt class="text-gray-500 dark:text-gray-400">Estimated notional</dt>
        <dd class="mt-1 font-semibold text-gray-900 dark:text-white">
          {{ formatCurrency(estimatedNotional) }}
        </dd>
      </div>
      <div class="rounded-lg bg-gray-50 p-3 dark:bg-gray-900">
        <dt class="text-gray-500 dark:text-gray-400">Fee (0.1%)</dt>
        <dd class="mt-1 font-semibold text-gray-900 dark:text-white">
          {{ formatCurrency(estimatedFee) }}
        </dd>
      </div>
    </dl>

    <p v-if="error" class="mt-3 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">
      {{ error }}
    </p>
    <p v-if="disabled && disabledReason" class="mt-3 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-700">
      {{ disabledReason }}
    </p>

    <button
      type="submit"
      class="mt-5 h-11 w-full rounded-lg bg-blue-600 text-sm font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
      :disabled="disabled || submitting || quantity <= 0 || (orderType === 'limit' && (!limitPrice || limitPrice <= 0))"
    >
      {{ submitting ? 'Submitting...' : `Submit ${orderType === 'limit' ? 'Limit' : 'Market'} ${side === 'buy' ? 'Buy' : 'Sell'}` }}
    </button>
  </form>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import type { CryptoSymbol, OrderSide } from '@/types/crypto'

const props = defineProps<{
  symbol: CryptoSymbol
  latestPrice: number
  error?: string
  submitting?: boolean
  disabled?: boolean
  disabledReason?: string
}>()

const emit = defineEmits<{
  submit: [
    order: {
      side: OrderSide
      quantity: number
      orderType: 'market' | 'limit'
      limitPrice?: number
      stopLossPrice?: number
      takeProfitPrice?: number
    },
  ]
}>()

const side = ref<OrderSide>('buy')
const orderType = ref<'market' | 'limit'>('market')
const quantity = ref(0.1)
const limitPrice = ref<number | undefined>(undefined)
const showTpSl = ref(false)
const takeProfitPrice = ref<number | undefined>(undefined)
const stopLossPrice = ref<number | undefined>(undefined)

watch(() => props.latestPrice, (newPrice) => {
  if (!limitPrice.value && newPrice > 0) {
    limitPrice.value = newPrice
  }
}, { immediate: true })

const effectivePrice = computed(() => (orderType.value === 'limit' && limitPrice.value ? limitPrice.value : props.latestPrice))
const estimatedNotional = computed(() => effectivePrice.value * quantity.value)
const estimatedFee = computed(() => estimatedNotional.value * 0.001)

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 2,
  }).format(value)
}

function handleSubmit() {
  emit('submit', {
    side: side.value,
    quantity: quantity.value,
    orderType: orderType.value,
    limitPrice: orderType.value === 'limit' ? limitPrice.value : undefined,
    stopLossPrice: showTpSl.value ? stopLossPrice.value : undefined,
    takeProfitPrice: showTpSl.value ? takeProfitPrice.value : undefined,
  })
}
</script>
