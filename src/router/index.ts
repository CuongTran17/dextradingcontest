import { createRouter, createWebHistory } from 'vue-router'

import { isAdmin, isLoggedIn } from '@/services/authApi'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  scrollBehavior(to, from, savedPosition) {
    return savedPosition || { left: 0, top: 0 }
  },
  routes: [
    {
      path: '/',
      name: 'CryptoDashboard',
      component: () => import('../views/CryptoDashboard.vue'),
      meta: { title: 'Crypto Contest Dashboard' },
    },
    {
      path: '/trade/:symbol?',
      name: 'CryptoTrade',
      component: () => import('../views/CryptoTrade.vue'),
      meta: { title: 'Trade Simulator' },
    },
    {
      path: '/contests',
      name: 'ContestList',
      component: () => import('../views/ContestList.vue'),
      meta: { title: 'Trading Contests' },
    },
    {
      path: '/contests/:contestId',
      name: 'ContestDetail',
      component: () => import('../views/ContestDetail.vue'),
      meta: { title: 'Contest Detail' },
    },
    {
      path: '/contests/:contestId/leaderboard',
      name: 'ContestLeaderboard',
      component: () => import('../views/ContestLeaderboard.vue'),
      meta: { title: 'Leaderboard' },
    },
    {
      path: '/portfolio',
      name: 'VirtualPortfolio',
      component: () => import('../views/VirtualPortfolio.vue'),
      meta: { title: 'Virtual Portfolio', requiresAuth: true },
    },
    {
      path: '/admin',
      name: 'AdminDashboard',
      component: () => import('../views/Admin/AdminDashboard.vue'),
      meta: { title: 'Admin', requiresAuth: true, requiresAdmin: true },
    },
    {
      path: '/signin',
      name: 'Signin',
      component: () => import('../views/Auth/Signin.vue'),
      meta: { title: 'Sign In' },
    },
    {
      path: '/signup',
      name: 'Signup',
      component: () => import('../views/Auth/Signup.vue'),
      meta: { title: 'Sign Up' },
    },
    {
      path: '/welcome',
      name: 'GuestGate',
      component: () => import('../views/Auth/GuestGate.vue'),
      meta: { title: 'Join Crypto Contest' },
    },
    {
      path: '/profile',
      name: 'Profile',
      component: () => import('../views/Profile.vue'),
      meta: { title: 'Profile', requiresAuth: true },
    },
    {
      path: '/:pathMatch(.*)*',
      redirect: '/',
      meta: { title: 'Crypto Contest Dashboard' },
    },
  ],
})

router.beforeEach((to, from, next) => {
  document.title = `${to.meta.title} | Crypto Contest`

  const publicRouteNames = new Set([
    'CryptoDashboard',
    'CryptoTrade',
    'ContestList',
    'ContestDetail',
    'ContestLeaderboard',
    'Signin',
    'Signup',
    'GuestGate',
  ])
  const guestOnlyRouteNames = new Set(['Signin', 'Signup', 'GuestGate'])
  const routeName = typeof to.name === 'string' ? to.name : ''
  const isPublicRoute = publicRouteNames.has(routeName)
  const isGuestOnlyRoute = guestOnlyRouteNames.has(routeName)

  if (!isLoggedIn() && !isPublicRoute) {
    return next({ name: 'Signin', query: { redirect: to.fullPath } })
  }

  if (isLoggedIn() && isGuestOnlyRoute) {
    return next({ name: 'CryptoDashboard' })
  }

  if (to.meta.requiresAuth && !isLoggedIn()) {
    return next({ name: 'Signin', query: { redirect: to.fullPath } })
  }

  if (to.meta.requiresAdmin && !isAdmin()) {
    return next({ name: 'CryptoDashboard' })
  }

  next()
})

export default router
