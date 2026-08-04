import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import UserMenu from '@/components/layout/header/UserMenu.vue'

const routerPush = vi.hoisted(() => vi.fn())
const applicationSignOut = vi.hoisted(() => vi.fn(async () => undefined))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: routerPush }),
}))

vi.mock('@/composables/useApplicationLogout', () => ({
  useApplicationLogout: () => ({ signOut: applicationSignOut }),
}))

vi.mock('@/services/authApi', () => ({
  getSavedUser: vi.fn(() => ({
    email: 'trader@example.com',
    avatar_data: null,
  })),
  isLoggedIn: vi.fn(() => true),
  logout: vi.fn(),
}))

describe('UserMenu', () => {
  beforeEach(() => {
    routerPush.mockClear()
    applicationSignOut.mockClear()
  })

  it('uses centralized wallet and account cleanup for header sign out', async () => {
    const wrapper = mount(UserMenu, {
      global: {
        stubs: {
          RouterLink: {
            props: ['to'],
            emits: ['click'],
            template: '<a :href="to" @click.prevent="$emit(\'click\', $event)"><slot /></a>',
          },
        },
      },
    })

    await wrapper.get('button').trigger('click')
    const signOutLink = wrapper.findAll('a').find((link) => link.text().includes('Sign Out'))
    expect(signOutLink).toBeDefined()

    await signOutLink!.trigger('click')
    await flushPromises()

    expect(applicationSignOut).toHaveBeenCalledOnce()
    expect(routerPush).toHaveBeenCalledWith('/welcome')
  })
})
