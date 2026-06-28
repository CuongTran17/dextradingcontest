<template>
  <div class="min-h-screen bg-gray-50 dark:bg-gray-900">
    <PageHeader title="Crypto Contest Admin">
      <span class="rounded-full border border-gray-200 bg-white px-3 py-1 text-xs font-medium text-gray-600 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300">
        {{ activeTabMeta.label }}
      </span>
    </PageHeader>

    <div class="mx-auto max-w-full px-6 py-6">
      <div
        class="grid gap-6 transition-all duration-300"
        :class="isSidebarCollapsed ? 'lg:grid-cols-[80px_minmax(0,1fr)]' : 'lg:grid-cols-[280px_minmax(0,1fr)]'"
      >
        <aside
          class="sticky top-24 flex self-start rounded-lg border border-gray-200 bg-white p-4 shadow-sm transition-all duration-300 dark:border-gray-800 dark:bg-white/[0.03]"
          :class="isSidebarCollapsed ? 'lg:w-[80px] w-full' : 'w-full lg:w-[280px]'"
        >
          <div class="w-full">
            <div class="flex items-center" :class="isSidebarCollapsed ? 'justify-center' : 'justify-between'">
              <p v-if="!isSidebarCollapsed" class="text-xs font-bold uppercase tracking-wide text-gray-500 dark:text-gray-400">
                Admin tabs
              </p>
              <button
                class="hidden rounded-lg p-1.5 text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-700 dark:text-gray-400 dark:hover:bg-gray-800 dark:hover:text-gray-200 lg:block"
                title="Toggle admin menu"
                @click="isSidebarCollapsed = !isSidebarCollapsed"
              >
                <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
                </svg>
              </button>
            </div>

            <div class="mt-4 hidden space-y-2 lg:block">
              <button
                v-for="tab in tabs"
                :key="tab.key"
                class="flex w-full rounded-lg border transition-all duration-200"
                :class="[
                  activeTab === tab.key
                    ? 'border-brand-500 bg-brand-50 dark:border-brand-500/60 dark:bg-brand-500/10'
                    : 'border-gray-200 bg-gray-50 hover:bg-gray-100 dark:border-gray-700 dark:bg-gray-800/60',
                  isSidebarCollapsed ? 'justify-center p-2' : 'items-start gap-3 px-4 py-3',
                ]"
                :title="isSidebarCollapsed ? tab.label : undefined"
                @click="setActiveTab(tab.key)"
              >
                <span
                  class="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full text-sm font-semibold"
                  :class="tab.badgeClass"
                >
                  {{ tab.shortLabel }}
                </span>
                <span v-if="!isSidebarCollapsed" class="min-w-0 text-left">
                  <span class="block text-sm font-semibold text-gray-800 dark:text-white/90">{{ tab.label }}</span>
                  <span class="mt-0.5 block text-xs leading-5 text-gray-500 dark:text-gray-400">{{ tab.description }}</span>
                </span>
              </button>
            </div>

            <div class="mt-4 flex gap-2 overflow-x-auto pb-1 lg:hidden">
              <button
                v-for="tab in tabs"
                :key="tab.key"
                class="whitespace-nowrap rounded-full border px-4 py-2 text-sm font-medium transition-colors"
                :class="activeTab === tab.key ? 'border-brand-500 bg-brand-500 text-white' : 'border-gray-200 bg-white text-gray-600 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300'"
                @click="setActiveTab(tab.key)"
              >
                {{ tab.label }}
              </button>
            </div>
          </div>
        </aside>

        <section class="min-w-0">
          <component :is="activeComponent" />
        </section>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import PageHeader from '@/components/layout/PageHeader.vue'
import TabAccounts from './components/TabAccounts.vue'
import TabContestParticipants from './components/TabContestParticipants.vue'
import TabContestResults from './components/TabContestResults.vue'
import TabContests from './components/TabContests.vue'
import TabOverview from './components/TabOverview.vue'
import TabUsers from './components/TabUsers.vue'

type AdminTab = 'overview' | 'users' | 'accounts' | 'contests' | 'participants' | 'results'

const tabs: Array<{
  key: AdminTab
  label: string
  shortLabel: string
  description: string
  badgeClass: string
}> = [
  {
    key: 'overview',
    label: 'Overview',
    shortLabel: 'O',
    description: 'Users, contests, accounts, and system totals.',
    badgeClass: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300',
  },
  {
    key: 'users',
    label: 'Users',
    shortLabel: 'U',
    description: 'Search users, roles, and lock status.',
    badgeClass: 'bg-violet-100 text-violet-700 dark:bg-violet-500/15 dark:text-violet-300',
  },
  {
    key: 'accounts',
    label: 'Accounts',
    shortLabel: 'A',
    description: 'Virtual balances, equity, positions, and orders.',
    badgeClass: 'bg-cyan-100 text-cyan-700 dark:bg-cyan-500/15 dark:text-cyan-300',
  },
  {
    key: 'contests',
    label: 'Contests',
    shortLabel: 'C',
    description: 'Contest status, dates, symbols, and initial capital.',
    badgeClass: 'bg-brand-100 text-brand-700 dark:bg-brand-500/15 dark:text-brand-300',
  },
  {
    key: 'participants',
    label: 'Participants',
    shortLabel: 'P',
    description: 'Wallets, equity, ROI, and trade counts.',
    badgeClass: 'bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300',
  },
  {
    key: 'results',
    label: 'Results',
    shortLabel: 'R',
    description: 'Final ranks and Phase B certificate/NFT status.',
    badgeClass: 'bg-sky-100 text-sky-700 dark:bg-sky-500/15 dark:text-sky-300',
  },
]

const route = useRoute()
const router = useRouter()
const activeTab = ref<AdminTab>('overview')
const isSidebarCollapsed = ref(localStorage.getItem('admin_sidebar_collapsed') === 'true')

watch(isSidebarCollapsed, (newVal) => {
  localStorage.setItem('admin_sidebar_collapsed', String(newVal))
})

const activeComponent = computed(() => {
  if (activeTab.value === 'users') return TabUsers
  if (activeTab.value === 'accounts') return TabAccounts
  if (activeTab.value === 'contests') return TabContests
  if (activeTab.value === 'participants') return TabContestParticipants
  if (activeTab.value === 'results') return TabContestResults
  return TabOverview
})
const activeTabMeta = computed(() => tabs.find((tab) => tab.key === activeTab.value) || tabs[0])

function resolveTab(value: unknown): AdminTab {
  return value === 'users'
    || value === 'accounts'
    || value === 'contests'
    || value === 'participants'
    || value === 'results'
    ? value
    : 'overview'
}

function setActiveTab(tab: AdminTab): void {
  activeTab.value = tab
  router.replace({
    path: '/admin',
    query: tab === 'overview' ? {} : { tab },
  })
}

watch(
  () => route.query.tab,
  (value) => {
    activeTab.value = resolveTab(value)
  },
  { immediate: true },
)
</script>
