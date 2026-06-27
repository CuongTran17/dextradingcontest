import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { login } from '@/services/authApi'
import Signin from '@/views/Auth/Signin.vue'

const push = vi.fn()
const routeState = vi.hoisted(() => ({ query: {} as Record<string, string> }))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push }),
  useRoute: () => routeState,
}))

vi.mock('@/components/layout/FullScreenLayout.vue', () => ({
  default: { template: '<div><slot /></div>' },
}))

vi.mock('@/services/authApi', () => ({
  login: vi.fn(),
}))

describe('Signin', () => {
  beforeEach(() => {
    push.mockReset()
    routeState.query = {}
    vi.mocked(login).mockReset()
    vi.mocked(login).mockResolvedValue({
      message: 'logged in',
      token: 'token-123',
      user: {
        id: 1,
        email: 'student@example.edu',
        phone: null,
        fullname: 'Nguyen An',
        avatar_data: null,
        role: 'user',
      },
    })
  })

  it('renders readable Vietnamese signin copy', () => {
    const wrapper = mount(Signin, {
      global: {
        stubs: {
          RouterLink: { template: '<a><slot /></a>' },
        },
      },
    })

    expect(wrapper.text()).toContain('Đăng nhập')
    expect(wrapper.text()).toContain('Mật khẩu')
    expect(wrapper.text()).toContain('Chưa có tài khoản?')
    expect(wrapper.text()).not.toContain('Ä')
    expect(wrapper.text()).not.toContain('Ã')
  })

  it('logs in and redirects to the requested route', async () => {
    routeState.query = { redirect: '/contests/practice-arena' }
    const wrapper = mount(Signin, {
      global: {
        stubs: {
          RouterLink: { template: '<a><slot /></a>' },
        },
      },
    })

    await wrapper.get('[data-test="signin-email"]').setValue('student@example.edu')
    await wrapper.get('[data-test="signin-password"]').setValue('secret123')
    await wrapper.get('[data-test="signin-form"]').trigger('submit')
    await flushPromises()

    expect(login).toHaveBeenCalledWith('student@example.edu', 'secret123')
    expect(push).toHaveBeenCalledWith('/contests/practice-arena')
  })

  it('shows a readable locked-account message', async () => {
    routeState.query = { locked: '1' }
    const wrapper = mount(Signin, {
      global: {
        stubs: {
          RouterLink: { template: '<a><slot /></a>' },
        },
      },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Tài khoản của bạn đã bị khóa')
  })
})
