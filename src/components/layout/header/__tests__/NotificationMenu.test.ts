import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import NotificationMenu from '../NotificationMenu.vue'

describe('NotificationMenu', () => {
  it('does not render TailAdmin sample notifications', async () => {
    const wrapper = mount(NotificationMenu, {
      global: {
        stubs: {
          RouterLink: { template: '<a><slot /></a>' },
        },
      },
    })

    await wrapper.find('button').trigger('click')

    expect(wrapper.text()).not.toContain('Terry Franci')
    expect(wrapper.text()).not.toContain('Nganter App')
    expect(wrapper.text()).toContain('No notifications')
  })
})
