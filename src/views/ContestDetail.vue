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
            :wallet-name="activeWalletName"
            :joined="joined"
            :joining="joining"
            :error="joinError"
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
import { useSolanaWalletSession } from '@/composables/useSolanaWalletSession'
import { DEFAULT_CONTEST_ID } from '@/constants/cryptoContests'
import { fetchContest } from '@/services/cryptoContestApi'
import { confirmSolanaJoin, fetchContestWallet } from '@/services/cryptoTradingApi'
import { joinContestOnchain } from '@/services/solanaWallet'
import type { Contest } from '@/types/crypto'

const route = useRoute()
const contest = ref<Contest | null>(null)
const loading = ref(true)
const loadError = ref('')
const joining = ref(false)
const joined = ref(false)
const joinedWallet = ref('')
const joinError = ref('')
const {
  walletAddress: connectedWallet,
  walletName,
  activeSigner,
  error: walletError,
} = useSolanaWalletSession()
const contestId = computed(() => String(route.params.contestId || DEFAULT_CONTEST_ID))
const activeWallet = computed(() => joinedWallet.value || connectedWallet.value)
const activeWalletName = computed(() => walletName.value)
const solanaReady = computed(() => Boolean(contest.value?.onchainInitializeTxSignature))
const adminWalletAddress = computed(() => contest.value?.onchainAdminWallet || '')
const adminWalletBlocked = computed(
  () => Boolean(activeWallet.value) && activeWallet.value === adminWalletAddress.value,
)
const solanaJoinBlockedReason = computed(() => {
  if (contest.value && !solanaReady.value) return 'Contest is not initialized on Solana yet.'
  if (adminWalletBlocked.value) return 'The admin wallet that initialized this contest cannot join it.'
  if (walletError.value) return walletError.value
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
    }
  } catch {
    joined.value = false
    joinedWallet.value = ''
  }
}

async function joinContest() {
  if (
    joining.value ||
    joined.value ||
    !contest.value ||
    !solanaReady.value ||
    adminWalletBlocked.value ||
    !connectedWallet.value
  ) {
    return
  }

  joining.value = true
  joinError.value = ''
  try {
    const pendingJoin = readPendingSolanaJoin(contest.value.id, activeWallet.value)
    const signer = activeSigner.value
    if (!pendingJoin && !signer) {
      joinError.value = 'Connect the wallet used to join this contest'
      return
    }
    const onchainJoin = pendingJoin ?? await joinContestOnchain(
      {
        contestId: contest.value.id,
        walletPublicKey: connectedWallet.value || undefined,
      },
      signer ?? undefined,
    )
    storePendingSolanaJoin(contest.value.id, onchainJoin)
    await confirmSolanaJoin({
      contestId: contest.value.id,
      walletAddress: onchainJoin.walletAddress,
      joinTxSignature: onchainJoin.signature,
    })
    joined.value = true
    joinedWallet.value = onchainJoin.walletAddress
    clearPendingSolanaJoin(contest.value.id, onchainJoin.walletAddress)
  } catch (error) {
    joinError.value = joinErrorMessage(error)
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

function pendingSolanaJoinKey(contestSlug: string, walletAddress: string): string {
  return `crypto_contest_pending_solana_join:${contestSlug}:${walletAddress}`
}

function readPendingSolanaJoin(
  contestSlug: string,
  walletAddress: string,
): { walletAddress: string; signature: string } | null {
  if (!walletAddress) return null
  const raw = localStorage.getItem(pendingSolanaJoinKey(contestSlug, walletAddress))
  if (!raw) return null
  try {
    const parsed = JSON.parse(raw) as { walletAddress?: string; signature?: string }
    if (parsed.walletAddress === walletAddress && parsed.signature) {
      return { walletAddress, signature: parsed.signature }
    }
  } catch {
    localStorage.removeItem(pendingSolanaJoinKey(contestSlug, walletAddress))
  }
  return null
}

function storePendingSolanaJoin(
  contestSlug: string,
  join: { walletAddress: string; signature: string },
): void {
  localStorage.setItem(
    pendingSolanaJoinKey(contestSlug, join.walletAddress),
    JSON.stringify(join),
  )
}

function clearPendingSolanaJoin(contestSlug: string, walletAddress: string): void {
  localStorage.removeItem(pendingSolanaJoinKey(contestSlug, walletAddress))
}

function joinErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message && error.message !== 'Unexpected error') {
    return error.message
  }
  return 'Unable to join on Solana. If you already approved a join transaction, click Join on Solana again to sync it with the backend.'
}

</script>
