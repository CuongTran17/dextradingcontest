<template>
  <main class="relative h-screen w-screen overflow-hidden bg-brand-950">
    <div class="absolute inset-0 bg-[radial-gradient(circle_at_30%_20%,rgba(37,99,235,0.55),transparent_35%),linear-gradient(135deg,#020617,#1e1b4b_45%,#064e3b)]"></div>

    <div class="relative z-10 flex h-full flex-col items-center justify-center px-6 text-center">
      <p class="mb-4 text-xs font-semibold uppercase tracking-[0.28em] text-brand-100/80">
        Crypto Contest
      </p>
      <h1 class="max-w-4xl text-4xl font-extrabold tracking-tight text-white sm:text-5xl md:text-6xl">
        JOIN WITH US
      </h1>
      <p class="mt-4 max-w-2xl text-sm text-brand-100/90 sm:text-base">
        Practice simulated crypto trading with virtual USDT_TEST and compete on educational leaderboards.
      </p>

      <button
        class="mt-10 rounded-lg border border-brand-200/70 bg-brand-500/90 px-10 py-4 text-base font-semibold tracking-wide text-white shadow-xl shadow-brand-900/40 transition hover:scale-[1.02] hover:bg-brand-500"
        @click="goToSignin"
      >
        JOIN WITH US
      </button>
    </div>
  </main>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()

const goToSignin = () => {
  router.push('/signin')
}
</script>
