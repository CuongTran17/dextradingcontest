import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import { reactive } from 'vue'

import AdminDashboard from '@/views/Admin/AdminDashboard.vue'

const route = reactive({ query: {} as Record<string, unknown> })
const replace = vi.fn()

vi.mock('vue-router', () => ({
  useRoute: () => route,
  useRouter: () => ({ replace }),
}))

vi.mock('@/components/layout/PageHeader.vue', () => ({
  default: { template: '<header><slot /></header>', props: ['title'] },
}))

vi.mock('@/views/Admin/components/TabOverview.vue', () => ({
  default: { template: '<section data-test="tab-overview">Overview</section>' },
}))

vi.mock('@/views/Admin/components/TabUsers.vue', () => ({
  default: { template: '<section data-test="tab-users">Users</section>' },
}))

vi.mock('@/views/Admin/components/TabAccounts.vue', () => ({
  default: { template: '<section data-test="tab-accounts">Accounts</section>' },
}))

vi.mock('@/views/Admin/components/TabContests.vue', () => ({
  default: { template: '<section data-test="tab-contests">Contests</section>' },
}))

vi.mock('@/views/Admin/components/TabContestParticipants.vue', () => ({
  default: { template: '<section data-test="tab-participants">Participants</section>' },
}))

vi.mock('@/views/Admin/components/TabContestResults.vue', () => ({
  default: { template: '<section data-test="tab-results">Results</section>' },
}))

describe('AdminDashboard', () => {
  it('shows overview by default and exposes users/accounts tabs', () => {
    route.query = {}

    const wrapper = mount(AdminDashboard)

    expect(wrapper.get('[data-test="tab-overview"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Users')
    expect(wrapper.text()).toContain('Accounts')
  })

  it('opens the accounts tab from query string', () => {
    route.query = { tab: 'accounts' }

    const wrapper = mount(AdminDashboard)

    expect(wrapper.get('[data-test="tab-accounts"]').exists()).toBe(true)
  })
})
