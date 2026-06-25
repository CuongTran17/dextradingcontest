import { beforeAll, describe, expect, it, vi } from 'vitest'

import router from '@/router'

async function navigateAsGuest(path: string) {
  window.localStorage.clear()
  await router.push(path)
  await router.isReady()
  return router.currentRoute.value
}

describe('router guest access', () => {
  beforeAll(() => {
    window.scrollTo = vi.fn()
  })

  it.each([
    ['/', 'CryptoDashboard'],
    ['/trade/BTCUSDT', 'CryptoTrade'],
    ['/contests', 'ContestList'],
    ['/contests/practice-arena', 'ContestDetail'],
    ['/contests/practice-arena/leaderboard', 'ContestLeaderboard'],
  ])('allows guests to open %s', async (path, routeName) => {
    const route = await navigateAsGuest(path)

    expect(route.name).toBe(routeName)
  })

  it.each([
    '/portfolio',
    '/profile',
    '/admin',
  ])('redirects guests from %s to signin with the original destination', async (path) => {
    const route = await navigateAsGuest(path)

    expect(route.name).toBe('Signin')
    expect(route.query.redirect).toBe(path)
  })

  it.each(['/premium', '/premium/checkout', '/premium/sepay-return'])(
    'removes legacy premium route %s',
    async (path) => {
      const route = await navigateAsGuest(path)

      expect(route.name).toBe('CryptoDashboard')
    },
  )
})
