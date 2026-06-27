import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { reactive } from 'vue'

import App from '@/App.vue'

const currentRoute = reactive({
  meta: {} as Record<string, unknown>,
})

vi.mock('vue-router', () => ({
  RouterView: { template: '<main data-test="router-view">Page</main>' },
  useRoute: () => currentRoute,
}))

vi.mock('@/components/layout/ThemeProvider.vue', () => ({
  default: { template: '<div data-test="theme-provider"><slot /></div>' },
}))

vi.mock('@/components/layout/SidebarProvider.vue', () => ({
  default: { template: '<div data-test="sidebar-provider"><slot /></div>' },
}))

vi.mock('@/components/layout/AdminLayout.vue', () => ({
  default: { template: '<section data-test="admin-layout"><slot /></section>' },
}))

describe('App', () => {
  beforeEach(() => {
    currentRoute.meta = {}
  })

  it('wraps main app routes in the admin sidebar layout', () => {
    const wrapper = mount(App)

    expect(wrapper.get('[data-test="admin-layout"]').exists()).toBe(true)
    expect(wrapper.get('[data-test="router-view"]').exists()).toBe(true)
  })

  it('keeps full-screen auth routes outside the sidebar layout', () => {
    currentRoute.meta = { layout: 'fullscreen' }
    const wrapper = mount(App)

    expect(wrapper.find('[data-test="admin-layout"]').exists()).toBe(false)
    expect(wrapper.get('[data-test="router-view"]').exists()).toBe(true)
  })
})
