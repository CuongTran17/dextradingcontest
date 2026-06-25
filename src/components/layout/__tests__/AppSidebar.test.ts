import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import AppSidebar from '../AppSidebar.vue'
import { DEFAULT_TRADE_PATH } from '@/constants/navigation'
import { isLoggedIn } from '@/services/authApi'

vi.mock('@/composables/useSidebar', () => ({
  useSidebar: () => ({
    isExpanded: { value: true },
    isMobileOpen: { value: false },
    isHovered: { value: false },
  }),
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ path: '/' }),
  useRouter: () => ({ push: vi.fn() }),
}))

vi.mock('@/services/authApi', () => ({
  isLoggedIn: vi.fn(() => false),
  isAdmin: vi.fn(() => false),
  isPremium: vi.fn(() => false),
  getSavedUser: vi.fn(() => null),
  logout: vi.fn(),
}))

describe('AppSidebar', () => {
  beforeEach(() => {
    vi.mocked(isLoggedIn).mockReturnValue(false)
  })

  it('uses centralized default crypto trade path', () => {
    const wrapper = mount(AppSidebar, {
      global: {
        stubs: {
          RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' },
        },
      },
    })

    expect(wrapper.html()).toContain(`href="${DEFAULT_TRADE_PATH}"`)
  })

  it('does not render premium or stock navigation', () => {
    vi.mocked(isLoggedIn).mockReturnValue(true)
    const wrapper = mount(AppSidebar, {
      global: {
        stubs: {
          RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' },
        },
      },
    })

    expect(wrapper.text()).not.toContain('Premium')
    expect(wrapper.text()).not.toContain('Stocks')
    expect(wrapper.text()).not.toContain('DNSE')
  })
})
