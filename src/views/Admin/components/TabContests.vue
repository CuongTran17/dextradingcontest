<template>
  <section class="rounded-lg border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
    <div class="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
      <h2 class="text-lg font-semibold text-gray-900 dark:text-white">Contest Management</h2>
      <button
        class="rounded-lg bg-blue-600 px-3 py-2 text-sm font-semibold text-white disabled:opacity-60"
        :disabled="loading"
        @click="loadContests"
      >
        Refresh
      </button>
    </div>

    <p v-if="error" class="mt-3 text-sm text-rose-600">{{ error }}</p>
    <p v-if="loading" class="mt-4 text-sm text-gray-500 dark:text-gray-400">Loading contests...</p>

    <div v-else class="mt-4 overflow-x-auto">
      <table class="min-w-full divide-y divide-gray-200 text-sm dark:divide-gray-800">
        <thead class="text-left text-xs uppercase text-gray-500 dark:text-gray-400">
          <tr>
            <th class="px-3 py-2">Title</th>
            <th class="px-3 py-2">Status</th>
            <th class="px-3 py-2">Initial Capital</th>
            <th class="px-3 py-2">Symbols</th>
            <th class="px-3 py-2">Start / End</th>
            <th class="px-3 py-2">Participants</th>
            <th class="px-3 py-2">Actions</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-100 dark:divide-gray-800">
          <tr v-for="contest in contests" :key="contest.id">
            <td class="px-3 py-3 font-medium text-gray-900 dark:text-white">{{ contest.title }}</td>
            <td class="px-3 py-3">
              <select
                class="rounded border border-gray-300 bg-white px-2 py-1 text-sm text-gray-700 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-200"
                :value="contest.rawStatus ?? contest.status"
                @change="changeStatus(contest, ($event.target as HTMLSelectElement).value as RawContestStatus)"
              >
                <option value="draft">draft</option>
                <option value="scheduled">scheduled</option>
                <option value="active">active</option>
                <option value="settling">settling</option>
                <option value="completed">completed</option>
                <option value="cancelled">cancelled</option>
              </select>
            </td>
            <td class="px-3 py-3 text-gray-700 dark:text-gray-300">{{ formatCurrency(contest.initialCapital) }}</td>
            <td class="px-3 py-3 text-gray-700 dark:text-gray-300">{{ contest.symbols.join(', ') }}</td>
            <td class="px-3 py-3 text-gray-500 dark:text-gray-400">{{ contest.startsAt || '-' }} / {{ contest.endsAt || '-' }}</td>
            <td class="px-3 py-3 text-gray-700 dark:text-gray-300">{{ contest.participantCount }}</td>
            <td class="px-3 py-3">
              <div class="flex flex-wrap gap-2">
                <button
                  class="rounded border border-gray-300 px-2 py-1 text-xs font-semibold text-gray-700 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-200 dark:hover:bg-gray-800"
                  type="button"
                  :data-test="`edit-contest-${contest.id}`"
                  @click="editContest(contest)"
                >
                  Edit
                </button>
                <button
                  v-if="!contest.onchainInitializeTxSignature"
                  class="rounded border border-blue-300 px-2 py-1 text-xs font-semibold text-blue-700 hover:bg-blue-50 disabled:opacity-60 dark:border-blue-700 dark:text-blue-300 dark:hover:bg-blue-950"
                  type="button"
                  :data-test="`initialize-onchain-${contest.id}`"
                  :disabled="initializingContestId === contest.id"
                  @click="initializeOnchain(contest.id)"
                >
                  {{ initializingContestId === contest.id ? 'Initializing...' : 'Initialize on Solana' }}
                </button>
                <span
                  v-else
                  class="rounded bg-emerald-100 px-2 py-1 text-xs font-semibold text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300"
                >
                  On-chain ready
                </span>
                <span
                  v-if="contest.onchainAdminWallet"
                  class="text-xs text-gray-500 dark:text-gray-400"
                  :title="contest.onchainAdminWallet"
                >
                  Admin wallet {{ shortAddress(contest.onchainAdminWallet) }}
                </span>
                <input
                  class="w-20 rounded border border-gray-300 bg-white px-2 py-1 text-xs text-gray-700 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-200"
                  type="number"
                  min="1"
                  max="100"
                  :data-test="`certificate-topn-${contest.id}`"
                  :value="certificateTopN(contest.id)"
                  @change="setCertificateTopN(contest.id, Number(($event.target as HTMLInputElement).value))"
                >
                <button
                  class="rounded border border-emerald-300 px-2 py-1 text-xs font-semibold text-emerald-700 hover:bg-emerald-50 disabled:opacity-60 dark:border-emerald-700 dark:text-emerald-300 dark:hover:bg-emerald-950"
                  type="button"
                  :data-test="`export-certificates-${contest.id}`"
                  :disabled="exportingContestId === contest.id"
                  @click="exportCertificates(contest.id)"
                >
                  {{ exportingContestId === contest.id ? 'Exporting...' : 'Export Top N Certificates' }}
                </button>
                <button
                  class="rounded border border-rose-300 px-2 py-1 text-xs font-semibold text-rose-700 hover:bg-rose-50 disabled:opacity-60 dark:border-rose-700 dark:text-rose-300 dark:hover:bg-rose-950"
                  type="button"
                  :data-test="`end-export-${contest.id}`"
                  :disabled="endingContestId === contest.id || contest.rawStatus === 'completed'"
                  @click="endAndExportContest(contest)"
                >
                  {{ endingContestId === contest.id ? 'Ending...' : 'End & Export Certificates' }}
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div
      v-if="certificateExport"
      class="mt-4 rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-950 dark:border-emerald-900 dark:bg-emerald-950/30 dark:text-emerald-100"
    >
      <p class="font-semibold">Certificates exported for {{ certificateExport.contest_id }}</p>
      <dl class="mt-3 grid gap-3 lg:grid-cols-3">
        <div>
          <dt class="text-xs uppercase text-emerald-700 dark:text-emerald-300">Batch</dt>
          <dd class="mt-1 font-semibold">Batch {{ certificateExport.batch_id }} · Top {{ certificateExport.top_n }}</dd>
        </div>
        <div>
          <dt class="text-xs uppercase text-emerald-700 dark:text-emerald-300">Merkle root</dt>
          <dd class="mt-1 break-all font-mono text-xs">{{ certificateExport.merkle_root }}</dd>
        </div>
        <div>
          <dt class="text-xs uppercase text-emerald-700 dark:text-emerald-300">Snapshot hash</dt>
          <dd class="mt-1 break-all font-mono text-xs">{{ certificateExport.snapshot_hash }}</dd>
        </div>
        <div>
          <dt class="text-xs uppercase text-emerald-700 dark:text-emerald-300">Claims exported</dt>
          <dd class="mt-1 font-semibold">Claims exported: {{ certificateExport.claims.length }}</dd>
        </div>
      </dl>
      <div class="mt-3 flex flex-wrap items-center gap-2">
        <button
          class="rounded bg-emerald-700 px-3 py-2 text-xs font-semibold text-white disabled:opacity-60"
          type="button"
          data-test="publish-certificate-root"
          :disabled="publishingCertificateRoot"
          @click="publishCertificateRoot"
        >
          {{ publishingCertificateRoot ? 'Publishing...' : 'Publish Root' }}
        </button>
        <p v-if="certificateAuthorizationStatus" class="text-xs font-semibold text-emerald-800 dark:text-emerald-200">
          {{ certificateAuthorizationStatus }}
        </p>
      </div>
    </div>

    <form
      class="mt-5 grid gap-3 border-t border-gray-100 pt-4 dark:border-gray-800 md:grid-cols-3"
      data-test="contest-form"
      @submit.prevent="saveContest"
    >
      <input
        v-model="form.slug"
        class="rounded-lg border border-gray-300 px-3 py-2 text-sm dark:border-gray-700 dark:bg-gray-900 dark:text-white"
        data-test="contest-slug"
        :disabled="Boolean(editingContestId)"
        placeholder="contest-slug"
        required
      >
      <input
        v-model="form.title"
        class="rounded-lg border border-gray-300 px-3 py-2 text-sm dark:border-gray-700 dark:bg-gray-900 dark:text-white"
        data-test="contest-title"
        placeholder="Contest title"
        required
      >
      <input
        v-model.number="form.initialBalance"
        class="rounded-lg border border-gray-300 px-3 py-2 text-sm dark:border-gray-700 dark:bg-gray-900 dark:text-white"
        data-test="contest-initial-balance"
        :disabled="Boolean(editingContestId)"
        min="1"
        type="number"
      >
      <input
        v-model="form.symbolsText"
        class="rounded-lg border border-gray-300 px-3 py-2 text-sm dark:border-gray-700 dark:bg-gray-900 dark:text-white md:col-span-2"
        data-test="contest-symbols"
        placeholder="BTCUSDT,ETHUSDT"
      >
      <input
        v-model="form.startsAt"
        class="rounded-lg border border-gray-300 px-3 py-2 text-sm dark:border-gray-700 dark:bg-gray-900 dark:text-white"
        data-test="contest-starts-at"
        type="datetime-local"
      >
      <input
        v-model="form.endsAt"
        class="rounded-lg border border-gray-300 px-3 py-2 text-sm dark:border-gray-700 dark:bg-gray-900 dark:text-white"
        data-test="contest-ends-at"
        type="datetime-local"
      >
      <div class="flex gap-2">
        <button class="rounded-lg bg-emerald-600 px-3 py-2 text-sm font-semibold text-white" type="submit">
          {{ editingContestId ? 'Update Contest' : 'Create Contest' }}
        </button>
        <button
          v-if="editingContestId"
          class="rounded-lg border border-gray-300 px-3 py-2 text-sm font-semibold text-gray-700 dark:border-gray-700 dark:text-gray-200"
          type="button"
          @click="resetForm"
        >
          Cancel
        </button>
      </div>
    </form>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import {
  confirmCertificateBatchAuthorization,
  confirmContestOnchainInitialize,
  createAdminCryptoContest,
  exportContestCertificates,
  fetchAdminCryptoContests,
  setAdminCryptoContestStatus,
  settleAdminCryptoContest,
  updateAdminCryptoContest,
  type CertificateExportResult,
} from '@/services/cryptoContestApi'
import {
  initializeContestOnchain,
  publishCertificateRootOnchain,
  setContestJoinEnabledOnchain,
} from '@/services/solanaWallet'
import { useSolanaWalletSession } from '@/composables/useSolanaWalletSession'
import type { Contest, CryptoSymbol, RawContestStatus } from '@/types/crypto'

const {
  walletAddress,
  activeSigner,
  connectWallet,
} = useSolanaWalletSession()
const contests = ref<Contest[]>([])
const loading = ref(false)
const error = ref('')
const editingContestId = ref('')
const exportingContestId = ref('')
const initializingContestId = ref('')
const endingContestId = ref('')
const certificateExport = ref<CertificateExportResult | null>(null)
const certificateTopNs = ref<Record<string, number>>({})
const publishingCertificateRoot = ref(false)
const certificateAuthorizationStatus = ref('')
const form = ref({
  slug: '',
  title: '',
  mode: 'contest' as const,
  status: 'draft' as const,
  initialBalance: 10000,
  symbolsText: 'BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT,BNBUSDT',
  startsAt: '',
  endsAt: '',
})

async function loadContests() {
  loading.value = true
  error.value = ''
  try {
    contests.value = await fetchAdminCryptoContests()
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Unable to load contests'
  } finally {
    loading.value = false
  }
}

async function saveContest() {
  error.value = ''
  try {
    const symbols = form.value.symbolsText
      .split(',')
      .map((item) => item.trim().toUpperCase())
      .filter(Boolean) as CryptoSymbol[]
    const startsAt = toIsoDateTime(form.value.startsAt)
    const endsAt = toIsoDateTime(form.value.endsAt)
    const slug = normalizeSlug(form.value.slug)
    form.value.slug = slug
    form.value.symbolsText = symbols.join(',')

    if (editingContestId.value) {
      const updated = await updateAdminCryptoContest(editingContestId.value, {
        title: form.value.title,
        symbols,
        startsAt,
        endsAt,
      })
      contests.value = contests.value.map((item) => (item.id === updated.id ? updated : item))
      resetForm()
      return
    }

    const created = await createAdminCryptoContest({
      slug,
      title: form.value.title,
      mode: form.value.mode,
      status: form.value.status,
      initialBalance: form.value.initialBalance,
      symbols,
      startsAt,
      endsAt,
    })
    contests.value = [created, ...contests.value]
    resetForm()
  } catch (err) {
    error.value = stepError(editingContestId.value ? 'Update contest' : 'Create contest', err)
  }
}

async function changeStatus(contest: Contest, status: RawContestStatus) {
  error.value = ''
  try {
    const updated = await setAdminCryptoContestStatus(contest.id, status)
    contests.value = contests.value.map((item) => (item.id === updated.id ? updated : item))
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Unable to update contest status'
  }
}

async function exportCertificates(contestId: string) {
  exportingContestId.value = contestId
  error.value = ''
  certificateAuthorizationStatus.value = ''
  try {
    certificateExport.value = await exportContestCertificates(contestId, {
      topN: certificateTopN(contestId),
    })
  } catch (err) {
    error.value = stepError('Export certificates', err)
  } finally {
    exportingContestId.value = ''
  }
}

async function initializeOnchain(contestId: string) {
  const signer = activeSigner.value
  if (!signer) {
    error.value = 'Connect the admin wallet before signing this Solana transaction'
    return
  }

  initializingContestId.value = contestId
  error.value = ''
  try {
    const onchain = await initializeContestOnchain({ contestId }, signer)
    const updated = await confirmContestOnchainInitialize({
      contestId,
      contestAddress: onchain.contestAddress,
      initializeTxSignature: onchain.signature,
      adminWallet: onchain.adminWallet,
    })
    contests.value = contests.value.map((item) => (item.id === updated.id ? updated : item))
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Unable to initialize contest on Solana'
  } finally {
    initializingContestId.value = ''
  }
}

async function endAndExportContest(contest: Contest) {
  if (!contest.onchainAdminWallet || !contest.onchainContestAddress || !contest.onchainInitializeTxSignature) {
    error.value = 'Initialize this contest on Solana before ending it'
    return
  }
  const adminWallet = contest.onchainAdminWallet
  const contestAddress = contest.onchainContestAddress
  const signer = activeSigner.value
  if (!signer) {
    error.value = 'Connect the admin wallet before signing this Solana transaction'
    return
  }

  endingContestId.value = contest.id
  error.value = ''
  try {
    await runStep('Close Solana joins', () =>
      setContestJoinEnabledOnchain({
        contestId: contest.id,
        contestAddress,
        enabled: false,
        expectedAdminWallet: adminWallet,
      }, signer),
    )
    const endedAt = new Date().toISOString()
    await runStep('Mark contest settling', () =>
      updateAdminCryptoContest(contest.id, { status: 'settling', endsAt: endedAt }),
    )
    await runStep('Settle contest', () => settleAdminCryptoContest(contest.id))
    certificateExport.value = await runStep('Export certificates', () =>
      exportContestCertificates(contest.id, {
        topN: certificateTopN(contest.id),
      }),
    )
    contests.value = contests.value.map((item) =>
      item.id === contest.id
        ? {
            ...item,
            status: 'ended',
            rawStatus: 'completed',
            endsAt: endedAt,
          }
        : item,
    )
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Unable to end and export contest'
  } finally {
    endingContestId.value = ''
  }
}

async function publishCertificateRoot() {
  if (!certificateExport.value) return
  const contest = contests.value.find((item) => item.id === certificateExport.value?.contest_id)
  if (!contest?.onchainAdminWallet || !contest.onchainContestAddress) {
    error.value = 'Initialize this contest on Solana before publishing certificate roots'
    return
  }
  const signer = activeSigner.value
  if (!signer) {
    error.value = 'Connect the admin wallet before signing this Solana transaction'
    return
  }

  publishingCertificateRoot.value = true
  error.value = ''
  certificateAuthorizationStatus.value = ''
  try {
    const onchain = await publishCertificateRootOnchain({
      contestId: certificateExport.value.contest_id,
      contestAddress: contest.onchainContestAddress,
      rootHex: certificateExport.value.merkle_root,
      snapshotHashHex: certificateExport.value.snapshot_hash,
      topN: certificateExport.value.top_n,
      batchId: certificateExport.value.batch_id,
      expectedAdminWallet: contest.onchainAdminWallet,
    }, signer)
    await confirmCertificateBatchAuthorization({
      contestId: certificateExport.value.contest_id,
      batchId: certificateExport.value.batch_id,
      adminWallet: onchain.adminWallet,
      authorizeTxSignature: onchain.signature,
    })
    certificateAuthorizationStatus.value = 'Certificate batch authorized on Solana'
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Unable to publish certificate root'
  } finally {
    publishingCertificateRoot.value = false
  }
}

onMounted(loadContests)

function editContest(contest: Contest) {
  editingContestId.value = contest.id
  form.value.slug = contest.id
  form.value.title = contest.title
  form.value.initialBalance = contest.initialCapital
  form.value.symbolsText = contest.symbols.join(',')
  form.value.startsAt = toDateTimeLocal(contest.startsAt)
  form.value.endsAt = toDateTimeLocal(contest.endsAt)
}

async function runStep<T>(label: string, action: () => Promise<T>): Promise<T> {
  try {
    return await action()
  } catch (err) {
    throw new Error(stepError(label, err))
  }
}

function stepError(label: string, err: unknown): string {
  const message = err instanceof Error && err.message ? err.message : 'Unexpected error'
  return `${label} failed: ${message}`
}

function resetForm() {
  editingContestId.value = ''
  form.value = {
    slug: '',
    title: '',
    mode: 'contest',
    status: 'draft',
    initialBalance: 10000,
    symbolsText: 'BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT,BNBUSDT',
    startsAt: '',
    endsAt: '',
  }
}

function normalizeSlug(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
}

function toIsoDateTime(value: string): string | null {
  if (!value) return null
  return new Date(value).toISOString()
}

function toDateTimeLocal(value: string): string {
  if (!value) return ''
  const date = new Date(value)
  const offsetMs = date.getTimezoneOffset() * 60_000
  return new Date(date.getTime() - offsetMs).toISOString().slice(0, 16)
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

function certificateTopN(contestId: string): number {
  return certificateTopNs.value[contestId] ?? 10
}

function setCertificateTopN(contestId: string, value: number) {
  const normalized = Number.isFinite(value) ? Math.trunc(value) : 10
  certificateTopNs.value = {
    ...certificateTopNs.value,
    [contestId]: Math.min(100, Math.max(1, normalized)),
  }
}
</script>
