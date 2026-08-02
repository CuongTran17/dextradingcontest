<template>
  <main class="space-y-6">
    <section class="rounded-lg border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
      <div class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p class="text-sm uppercase text-gray-500 dark:text-gray-400">{{ contestId }}</p>
          <h1 class="mt-1 text-2xl font-semibold text-gray-900 dark:text-white">My Certificate</h1>
        </div>
        <span
          v-if="certificate?.eligible"
          class="w-fit rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-700"
        >
          Rank #{{ certificate.rank }}
        </span>
      </div>

      <p v-if="loading" class="mt-5 text-sm text-gray-500 dark:text-gray-400">Loading certificate...</p>
      <p v-else-if="error" class="mt-5 text-sm text-rose-600">{{ error }}</p>
      <p v-else-if="!certificate?.eligible" class="mt-5 text-sm text-gray-500 dark:text-gray-400">
        No certificate is available for this contest.
      </p>

      <div v-else class="mt-6 grid gap-5 lg:grid-cols-[320px_1fr]">
        <img
          v-if="certificate.imageUri"
          :src="ipfsGateway(certificate.imageUri)"
          alt="Contest certificate"
          class="aspect-[4/3] w-full rounded-lg border border-gray-200 object-cover dark:border-gray-800"
        >

        <div class="space-y-4 text-sm text-gray-600 dark:text-gray-300">
          <div>
            <p class="text-lg font-semibold text-gray-900 dark:text-white">{{ certificate.recipientName }}</p>
            <p class="mt-1">{{ shortWallet(certificate.walletAddress || '') }}</p>
          </div>

          <dl class="grid gap-3 sm:grid-cols-2">
            <div class="rounded-lg bg-gray-50 p-3 dark:bg-gray-900">
              <dt class="text-xs text-gray-500 dark:text-gray-400">Batch</dt>
              <dd class="mt-1 break-all font-medium text-gray-900 dark:text-white">
                {{ certificate.batchId ? `Batch ${certificate.batchId} · Top ${certificate.topN}` : 'Pending' }}
              </dd>
            </div>
            <div class="rounded-lg bg-gray-50 p-3 dark:bg-gray-900">
              <dt class="text-xs text-gray-500 dark:text-gray-400">Metadata</dt>
              <dd class="mt-1 break-all font-medium text-gray-900 dark:text-white">
                {{ certificate.metadataUri }}
              </dd>
            </div>
            <div class="rounded-lg bg-gray-50 p-3 dark:bg-gray-900">
              <dt class="text-xs text-gray-500 dark:text-gray-400">Transaction</dt>
              <dd class="mt-1 break-all font-medium text-gray-900 dark:text-white">
                {{ certificate.mintTxSignature || 'Pending' }}
              </dd>
            </div>
          </dl>

          <button
            data-testid="claim-certificate"
            class="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
            :disabled="claiming || Boolean(certificate.mintTxSignature)"
            @click="claim"
          >
            {{ certificate.mintTxSignature ? 'Claimed' : claiming ? 'Claiming...' : 'Mint Certificate' }}
          </button>
        </div>
      </div>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import {
  confirmCertificateClaim,
  fetchMyCertificate,
  type CertificateClaimStatus,
} from '@/services/cryptoTradingApi'
import { claimCertificateOnchain } from '@/services/solanaWallet'
import { useSolanaWalletSession } from '@/composables/useSolanaWalletSession'

const route = useRoute()
const certificate = ref<CertificateClaimStatus | null>(null)
const loading = ref(true)
const claiming = ref(false)
const error = ref('')
const contestId = computed(() => String(route.params.contestId || 'practice-arena'))
const { walletAddress, connectWallet } = useSolanaWalletSession()

onMounted(async () => {
  try {
    certificate.value = await fetchMyCertificate(contestId.value)
  } catch (loadError) {
    error.value = loadError instanceof Error ? loadError.message : 'Unable to load certificate'
  } finally {
    loading.value = false
  }
})

async function claim() {
  if (claiming.value || !certificate.value?.eligible || certificate.value.mintTxSignature) return
  if (
    !certificate.value.walletAddress ||
    !certificate.value.batchId ||
    !certificate.value.topN ||
    !certificate.value.batchAuthorized ||
    certificate.value.rank === null ||
    !certificate.value.metadataUri ||
    !certificate.value.snapshotHash
  ) {
    error.value = 'Certificate claim is missing required on-chain data'
    return
  }

  const activeWallet = walletAddress.value
    ? { walletAddress: walletAddress.value }
    : await connectWallet()
  if (!activeWallet?.walletAddress) {
    error.value = 'Connect the wallet used to join this contest'
    return
  }
  if (activeWallet.walletAddress !== certificate.value.walletAddress) {
    error.value = 'Connect the wallet used to join this contest'
    return
  }

  claiming.value = true
  error.value = ''
  try {
    const onchainClaim = await claimCertificateOnchain({
      contestId: contestId.value,
      batchId: certificate.value.batchId,
      topN: certificate.value.topN,
      walletPublicKey: certificate.value.walletAddress,
      rank: certificate.value.rank,
      metadataUri: certificate.value.metadataUri,
      snapshotHash: certificate.value.snapshotHash,
      proof: certificate.value.proof,
    })
    certificate.value = await confirmCertificateClaim({
      contestId: contestId.value,
      batchId: certificate.value.batchId,
      mintTxSignature: onchainClaim.signature,
    })
  } catch (claimError) {
    error.value = claimError instanceof Error ? claimError.message : 'Unable to claim certificate'
  } finally {
    claiming.value = false
  }
}

function ipfsGateway(uri: string): string {
  if (uri.startsWith('ipfs://')) {
    return `https://gateway.pinata.cloud/ipfs/${uri.slice('ipfs://'.length)}`
  }
  return uri
}

function shortWallet(value: string): string {
  if (!value) return ''
  return `${value.slice(0, 4)}...${value.slice(-4)}`
}
</script>
