<template>
  <div class="hidden lg:block">
    <form @submit.prevent="submitSearch">
      <div class="relative">
        <button type="submit" class="absolute -translate-y-1/2 left-4 top-1/2">
          <svg
            class="fill-gray-500 dark:fill-gray-400"
            width="20"
            height="20"
            viewBox="0 0 20 20"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              fill-rule="evenodd"
              clip-rule="evenodd"
              d="M3.04175 9.37363C3.04175 5.87693 5.87711 3.04199 9.37508 3.04199C12.8731 3.04199 15.7084 5.87693 15.7084 9.37363C15.7084 12.8703 12.8731 15.7053 9.37508 15.7053C5.87711 15.7053 3.04175 12.8703 3.04175 9.37363ZM9.37508 1.54199C5.04902 1.54199 1.54175 5.04817 1.54175 9.37363C1.54175 13.6991 5.04902 17.2053 9.37508 17.2053C11.2674 17.2053 13.003 16.5344 14.357 15.4176L17.177 18.238C17.4699 18.5309 17.9448 18.5309 18.2377 18.238C18.5306 17.9451 18.5306 17.4703 18.2377 17.1774L15.418 14.3573C16.5365 13.0033 17.2084 11.2669 17.2084 9.37363C17.2084 5.04817 13.7011 1.54199 9.37508 1.54199Z"
              fill=""
            />
          </svg>
        </button>
        <input
          ref="searchInput"
          v-model="query"
          type="text"
          placeholder="Search BTCUSDT, ETHUSDT, SOLUSDT"
          @focus="showSuggestions = true"
          @input="showSuggestions = true"
          @keydown.down.prevent="highlightNext"
          @keydown.up.prevent="highlightPrev"
          @keydown.enter.prevent="submitSearch"
          @blur="handleBlur"
          class="dark:bg-dark-900 h-11 w-full rounded-lg border border-gray-200 bg-transparent py-2.5 pl-12 pr-14 text-sm text-gray-800 shadow-theme-xs placeholder:text-gray-400 focus:border-brand-300 focus:outline-hidden focus:ring-3 focus:ring-brand-500/10 dark:border-gray-800 dark:bg-gray-900 dark:bg-white/[0.03] dark:text-white/90 dark:placeholder:text-white/30 dark:focus:border-brand-800 xl:w-[430px]"
        />

        <div
          v-if="showSuggestions && filteredOptions.length > 0"
          class="absolute left-0 right-0 z-50 mt-1 max-h-72 overflow-auto rounded-lg border border-gray-200 bg-white shadow-xl dark:border-gray-700 dark:bg-gray-800"
        >
          <button
            v-for="(option, index) in filteredOptions"
            :key="option.symbol"
            type="button"
            @mousedown.prevent="selectOption(option.symbol)"
            class="flex w-full items-center justify-between px-3 py-2 text-left text-sm"
            :class="index === highlightedIndex ? 'bg-gray-100 dark:bg-gray-700' : 'hover:bg-gray-50 dark:hover:bg-gray-700/60'"
          >
            <span class="font-medium text-gray-800 dark:text-gray-100">{{ option.symbol }}</span>
            <span class="text-xs text-gray-500 dark:text-gray-400">{{ option.displayName }}</span>
          </button>
        </div>

        <button
          type="button"
          class="absolute right-2.5 top-1/2 inline-flex -translate-y-1/2 items-center gap-0.5 rounded-lg border border-gray-200 bg-gray-50 px-[7px] py-[4.5px] text-xs text-gray-500 dark:border-gray-800 dark:bg-white/[0.03] dark:text-gray-400"
          @click="focusInput"
        >
          <span>Ctrl</span>
          <span>K</span>
        </button>
      </div>
    </form>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'

import { CRYPTO_ASSETS } from '@/constants/cryptoAssets'
import type { CryptoSymbol } from '@/types/crypto'

const router = useRouter()
const query = ref('')
const showSuggestions = ref(false)
const highlightedIndex = ref(0)
const searchInput = ref<HTMLInputElement | null>(null)

const normalizedQuery = computed(() => query.value.trim().toUpperCase())
const filteredOptions = computed(() => {
  const keyword = normalizedQuery.value
  if (!keyword) return CRYPTO_ASSETS
  return CRYPTO_ASSETS.filter((asset) => {
    return asset.symbol.includes(keyword) || asset.displayName.toUpperCase().includes(keyword)
  })
})

function focusInput() {
  searchInput.value?.focus()
}

async function navigateToSymbol(symbol: CryptoSymbol): Promise<void> {
  await router.push(`/trade/${symbol}`)
  query.value = ''
  showSuggestions.value = false
  highlightedIndex.value = 0
}

async function submitSearch() {
  const selected = filteredOptions.value[Math.min(highlightedIndex.value, filteredOptions.value.length - 1)]
  if (selected) await navigateToSymbol(selected.symbol)
}

function selectOption(symbol: CryptoSymbol) {
  void navigateToSymbol(symbol)
}

function highlightNext() {
  if (!showSuggestions.value) showSuggestions.value = true
  highlightedIndex.value = Math.min(highlightedIndex.value + 1, filteredOptions.value.length - 1)
}

function highlightPrev() {
  if (!showSuggestions.value) showSuggestions.value = true
  highlightedIndex.value = Math.max(highlightedIndex.value - 1, 0)
}

function handleBlur() {
  setTimeout(() => {
    showSuggestions.value = false
  }, 120)
}
</script>
