<template>
  <main class="space-y-6">
    <SimulationDisclaimer />
    <p v-if="loading" class="text-sm text-gray-500 dark:text-gray-400">Loading contest...</p>
    <p v-else-if="loadError" class="text-sm text-rose-600">{{ loadError }}</p>
    <section
      v-else-if="contest"
      class="rounded-lg border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]"
    >
      <div class="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <p class="text-sm uppercase text-gray-500 dark:text-gray-400">{{ contest.status }}</p>
          <h1 class="mt-1 text-2xl font-semibold text-gray-900 dark:text-white">{{ contest.title }}</h1>
          <p class="mt-2 text-sm text-gray-500 dark:text-gray-400">
            Trade {{ contest.symbols.join(', ') }} with {{ formatCurrency(contest.initialCapital) }} virtual capital.
          </p>
        </div>
        <div class="flex flex-col gap-2 sm:flex-row">
          <SolanaWalletConnect
            :wallet-address="activeWallet"
            :wallet-name="walletName"
            :joined="joined"
            :connecting="connectingWallet"
            :joining="joining"
            :error="joinError"
            @connect="connectWallet"
            @join="joinContest"
          />
          <router-link
            class="rounded-lg bg-gray-900 px-4 py-2 text-sm font-semibold text-white dark:bg-white dark:text-gray-900"
            :to="`/contests/${contest.id}/trade/${contest.symbols[0] || 'BTCUSDT'}`"
          >
            Trade
          </router-link>
          <router-link
            class="rounded-lg border border-gray-300 px-4 py-2 text-sm font-semibold text-gray-700 dark:border-gray-700 dark:text-gray-200"
            :to="`/contests/${contest.id}/leaderboard`"
          >
            Leaderboard
          </router-link>
          <router-link
            class="rounded-lg border border-gray-300 px-4 py-2 text-sm font-semibold text-gray-700 dark:border-gray-700 dark:text-gray-200"
            :to="`/contests/${contest.id}/certificates`"
          >
            Certificate
          </router-link>
        </div>
      </div>
      <div class="mt-4 space-y-1">
        <p
          v-if="adminWalletAddress"
          class="text-xs text-gray-500 dark:text-gray-400"
          :title="adminWalletAddress"
        >
          Admin wallet {{ shortAddress(adminWalletAddress) }}
        </p>
        <p v-if="solanaJoinBlockedReason" class="text-sm text-amber-600 dark:text-amber-300">
          {{ solanaJoinBlockedReason }}
        </p>
      </div>

      <dl class="mt-6 grid gap-3 md:grid-cols-4">
        <div class="rounded-lg bg-gray-50 p-3 dark:bg-gray-900">
          <dt class="text-xs text-gray-500 dark:text-gray-400">Starts</dt>
          <dd class="mt-1 text-sm font-semibold text-gray-900 dark:text-white">{{ contest.startsAt }}</dd>
        </div>
        <div class="rounded-lg bg-gray-50 p-3 dark:bg-gray-900">
          <dt class="text-xs text-gray-500 dark:text-gray-400">Ends</dt>
          <dd class="mt-1 text-sm font-semibold text-gray-900 dark:text-white">{{ contest.endsAt }}</dd>
        </div>
        <div class="rounded-lg bg-gray-50 p-3 dark:bg-gray-900">
          <dt class="text-xs text-gray-500 dark:text-gray-400">Participants</dt>
          <dd class="mt-1 text-sm font-semibold text-gray-900 dark:text-white">{{ contest.participantCount }}</dd>
        </div>
        <div class="rounded-lg bg-gray-50 p-3 dark:bg-gray-900">
          <dt class="text-xs text-gray-500 dark:text-gray-400">Mode</dt>
          <dd class="mt-1 text-sm font-semibold text-gray-900 dark:text-white">{{ contest.mode }}</dd>
        </div>
      </dl>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import SimulationDisclaimer from '@/components/crypto/SimulationDisclaimer.vue'
import SolanaWalletConnect from '@/components/crypto/SolanaWalletConnect.vue'
import { DEFAULT_CONTEST_ID } from '@/constants/cryptoContests'
import { fetchContest } from '@/services/cryptoContestApi'
import { confirmSolanaJoin, fetchContestWallet } from '@/services/cryptoTradingApi'
import { connectSolanaWallet, joinContestOnchain } from '@/services/solanaWallet'
import type { Contest } from '@/types/crypto'

const route = useRoute()
const contest = ref<Contest | null>(null)
const loading = ref(true)
const loadError = ref('')
const connectingWallet = ref(false)
const joining = ref(false)
const joined = ref(false)
const connectedWallet = ref('')
const joinedWallet = ref('')
const walletName = ref('Solana wallet')
const joinError = ref('')
const contestId = computed(() => String(route.params.contestId || DEFAULT_CONTEST_ID))
const activeWallet = computed(() => joinedWallet.value || connectedWallet.value)
const solanaReady = computed(() => Boolean(contest.value?.onchainInitializeTxSignature))
const adminWalletAddress = computed(() => contest.value?.onchainAdminWallet || '')
const adminWalletBlocked = computed(
  () => Boolean(activeWallet.value) && activeWallet.value === adminWalletAddress.value,
)
const solanaJoinBlockedReason = computed(() => {
  if (contest.value && !solanaReady.value) return 'Contest is not initialized on Solana yet.'
  if (adminWalletBlocked.value) return 'The admin wallet that initialized this contest cannot join it.'
  return ''
})

onMounted(async () => {
  try {
    contest.value = await fetchContest(contestId.value)
    await loadWalletState()
  } catch (error) {
    loadError.value = error instanceof Error ? error.message : 'Unable to load contest'
  } finally {
    loading.value = false
  }
})

async function loadWalletState() {
  try {
    const wallet = await fetchContestWallet(contestId.value)
    if (wallet.wallet_address) {
      joined.value = true
      joinedWallet.value = wallet.wallet_address
      connectedWallet.value = wallet.wallet_address
    }
  } catch {
    joined.value = false
    joinedWallet.value = ''
  }
}

async function connectWallet() {
  if (connectingWallet.value || joined.value) return

  connectingWallet.value = true
  joinError.value = ''
  try {
    const wallet = await connectSolanaWallet()
    connectedWallet.value = wallet.walletAddress
    walletName.value = wallet.walletName
  } catch (error) {
    joinError.value = error instanceof Error ? error.message : 'Unable to connect Solana wallet'
  } finally {
    connectingWallet.value = false
  }
}

async function joinContest() {
  if (
    joining.value ||
    joined.value ||
    !contest.value ||
    !solanaReady.value ||
    adminWalletBlocked.value
  ) {
    return
  }

  joining.value = true
  joinError.value = ''
  try {
    const onchainJoin = await joinContestOnchain({
      contestId: contest.value.id,
      walletPublicKey: connectedWallet.value || undefined,
    })
    await confirmSolanaJoin({
      contestId: contest.value.id,
      walletAddress: onchainJoin.walletAddress,
      joinTxSignature: onchainJoin.signature,
    })
    joined.value = true
    joinedWallet.value = onchainJoin.walletAddress
  } catch (error) {
    joinError.value = error instanceof Error ? error.message : 'Unable to join contest'
  } finally {
    joining.value = false
  }
}

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(value)
}

function shortAddress(address: string): string {
  return `${address.slice(0, 4)}...${address.slice(-4)}`
}

</script>
