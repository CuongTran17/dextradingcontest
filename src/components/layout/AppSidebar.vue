<template>
  <aside
    :class="[
      'fixed left-0 top-0 z-99999 mt-16 flex h-screen flex-col border-r border-gray-200 bg-white px-4 text-gray-900 transition-all duration-300 ease-in-out dark:border-gray-800 dark:bg-gray-900 lg:mt-0',
      {
        'lg:w-[290px]': isExpanded || isMobileOpen || isHovered,
        'lg:w-[90px]': !isExpanded && !isHovered,
        'translate-x-0 w-[290px]': isMobileOpen,
        '-translate-x-full': !isMobileOpen,
        'lg:translate-x-0': true,
      },
    ]"
    @mouseenter="!isExpanded && (isHovered = true)"
    @mouseleave="isHovered = false"
  >
    <div :class="['flex py-7', !isExpanded && !isHovered ? 'lg:justify-center' : 'justify-start']">
      <router-link to="/">
        <img
          v-if="isExpanded || isHovered || isMobileOpen"
          class="dark:hidden"
          src="/images/logo/logo.svg"
          alt="Logo"
          width="150"
          height="40"
        />
        <img
          v-if="isExpanded || isHovered || isMobileOpen"
          class="hidden dark:block"
          src="/images/logo/logo-dark.svg"
          alt="Logo"
          width="150"
          height="40"
        />
        <img v-else src="/images/logo/logo-icon.svg" alt="Logo" width="32" height="32" />
      </router-link>
    </div>

    <div class="flex flex-col overflow-y-auto duration-300 ease-linear no-scrollbar">
      <nav class="mb-6">
        <div class="flex flex-col gap-6">
          <div v-for="menuGroup in menuGroups" :key="menuGroup.title">
            <h2
              :class="[
                'mb-3 flex text-xs uppercase leading-[20px] text-gray-400',
                !isExpanded && !isHovered ? 'lg:justify-center' : 'justify-start',
              ]"
            >
              <template v-if="isExpanded || isHovered || isMobileOpen">
                {{ menuGroup.title }}
              </template>
              <HorizontalDots v-else />
            </h2>
            <ul class="flex flex-col gap-2">
              <li v-for="item in menuGroup.items" :key="item.name">
                <router-link
                  :to="item.path"
                  :class="[
                    'menu-item group',
                    {
                      'menu-item-active': isActive(item.path),
                      'menu-item-inactive': !isActive(item.path),
                    },
                  ]"
                  @click="handleMenuClick($event, item.path)"
                >
                  <span :class="isActive(item.path) ? 'menu-item-icon-active' : 'menu-item-icon-inactive'">
                    <component :is="item.icon" />
                  </span>
                  <span v-if="isExpanded || isHovered || isMobileOpen" class="menu-item-text">
                    {{ item.name }}
                  </span>
                </router-link>
              </li>
            </ul>
          </div>
        </div>
      </nav>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useSidebar } from '@/composables/useSidebar'
import { DEFAULT_TRADE_PATH } from '@/constants/navigation'
import {
  BarChartIcon,
  BoxCubeIcon,
  HorizontalDots,
  LayoutDashboardIcon,
  ListIcon,
  LogoutIcon,
  UserCircleIcon,
} from '@/icons'
import { isAdmin, isLoggedIn, logout as authLogout } from '@/services/authApi'

const route = useRoute()
const router = useRouter()
const { isExpanded, isMobileOpen, isHovered } = useSidebar()

const menuGroups = computed(() => {
  const groups = [
    {
      title: 'Crypto Contest',
      items: [
        { icon: LayoutDashboardIcon, name: 'Dashboard', path: '/' },
        { icon: BarChartIcon, name: 'Trade Simulator', path: DEFAULT_TRADE_PATH },
        { icon: ListIcon, name: 'Contests', path: '/contests' },
        { icon: LayoutDashboardIcon, name: 'Leaderboard', path: '/contests/practice-arena/leaderboard' },
        { icon: BoxCubeIcon, name: 'Virtual Portfolio', path: '/portfolio' },
      ],
    },
  ]

  if (isLoggedIn()) {
    const userItems: { icon: any; name: string; path: string }[] = [
      { icon: UserCircleIcon, name: 'Profile', path: '/profile' },
    ]

    userItems.push({ icon: LogoutIcon, name: 'Sign Out', path: '/logout' })
    groups.push({ title: 'Account', items: userItems })
  } else {
    groups.push({
      title: 'Account',
      items: [
        { icon: UserCircleIcon, name: 'Sign In', path: '/signin' },
        { icon: UserCircleIcon, name: 'Sign Up', path: '/signup' },
      ],
    })
  }

  if (isAdmin()) {
    groups.push({
      title: 'Admin',
      items: [{ icon: LayoutDashboardIcon, name: 'Admin', path: '/admin' }],
    })
  }

  return groups
})

function isActive(path: string): boolean {
  if (path === '/logout') return false
  if (path.startsWith('/trade/')) return route.path.startsWith('/trade/')
  return route.path === path
}

function handleMenuClick(event: Event, path: string): void {
  if (path !== '/logout') return

  event.preventDefault()
  authLogout()
  router.push('/welcome')
}
</script>
