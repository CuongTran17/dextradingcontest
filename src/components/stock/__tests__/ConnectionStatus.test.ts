import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import ConnectionStatus from '@/components/stock/ConnectionStatus.vue'

describe('ConnectionStatus', () => {
  it('shows stale data instead of live when the connected socket carries an old timestamp', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-06-04T15:00:00+07:00'))

    const wrapper = mount(ConnectionStatus, {
      props: {
        connected: true,
        backendAvailable: true,
        lastUpdate: new Date('2026-06-04T14:45:00+07:00'),
      },
    })

    expect(wrapper.text()).toContain('Dữ liệu cũ')
    expect(wrapper.text()).not.toContain('Trực tiếp')
  })
})
