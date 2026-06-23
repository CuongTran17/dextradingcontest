import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import CryptoTrade from '@/views/CryptoTrade.vue'

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { symbol: 'BTCUSDT' } }),
  useRouter: () => ({ push: vi.fn() }),
}))

vi.mock('@/components/crypto/CryptoChart.vue', () => ({
  default: { template: '<div data-test="crypto-chart">BTCUSDT chart</div>' },
}))

vi.mock('@/components/crypto/OrderBook.vue', () => ({
  default: { template: '<div data-test="order-book">Order Book BTCUSDT</div>' },
}))

describe('CryptoTrade', () => {
  it('renders simulator safety language and BTCUSDT order controls', () => {
    const wrapper = mount(CryptoTrade)

    expect(wrapper.text()).toContain('Educational simulator')
    expect(wrapper.text()).toContain('BTCUSDT')
    expect(wrapper.text()).toContain('Buy')
    expect(wrapper.text()).toContain('Sell')
    expect(wrapper.text()).toContain('Order Book')
  })
})
