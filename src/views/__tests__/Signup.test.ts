import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { register } from '@/services/authApi'
import Signup from '@/views/Auth/Signup.vue'

const push = vi.fn()

vi.mock('vue-router', () => ({
  useRouter: () => ({ push }),
}))

vi.mock('@/components/layout/FullScreenLayout.vue', () => ({
  default: { template: '<div><slot /></div>' },
}))

vi.mock('@/services/authApi', () => ({
  register: vi.fn(),
}))

describe('Signup', () => {
  beforeEach(() => {
    push.mockReset()
    vi.mocked(register).mockReset()
    vi.mocked(register).mockResolvedValue({
      message: 'registered',
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

  it('registers a student account and redirects to contests', async () => {
    const wrapper = mount(Signup, {
      global: {
        stubs: {
          RouterLink: { template: '<a><slot /></a>' },
        },
      },
    })

    await wrapper.get('[data-test="signup-fullname"]').setValue('Nguyen An')
    await wrapper.get('[data-test="signup-email"]').setValue('student@example.edu')
    await wrapper.get('[data-test="signup-password"]').setValue('secret123')
    await wrapper.get('[data-test="signup-agreement"]').setValue(true)
    await wrapper.get('[data-test="signup-form"]').trigger('submit')
    await flushPromises()

    expect(register).toHaveBeenCalledWith('student@example.edu', 'secret123', 'Nguyen An')
    expect(push).toHaveBeenCalledWith('/contests')
  })

  it('shows a validation message when the agreement is missing', async () => {
    const wrapper = mount(Signup, {
      global: {
        stubs: {
          RouterLink: { template: '<a><slot /></a>' },
        },
      },
    })

    await wrapper.get('[data-test="signup-fullname"]').setValue('Nguyen An')
    await wrapper.get('[data-test="signup-email"]').setValue('student@example.edu')
    await wrapper.get('[data-test="signup-password"]').setValue('secret123')
    await wrapper.get('[data-test="signup-form"]').trigger('submit')

    expect(register).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('đồng ý')
  })
})
