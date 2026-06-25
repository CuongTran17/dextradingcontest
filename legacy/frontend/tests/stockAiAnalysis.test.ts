import { describe, expect, it } from 'vitest'
import { DECISION_ORDER, MODEL_LABELS, NEGATIVE_TOKENS, POSITIVE_TOKENS } from '../stockAiAnalysis'

describe('stockAiAnalysis constants', () => {
  it('exports stable decision order and non-empty token lists', () => {
    expect(DECISION_ORDER).toEqual(['Strong Buy', 'Buy', 'Hold', 'Sell', 'Strong Sell'])
    expect(POSITIVE_TOKENS.length).toBeGreaterThan(0)
    expect(NEGATIVE_TOKENS.length).toBeGreaterThan(0)
    expect(MODEL_LABELS.primary).toBe('VN30 Analyst AI')
  })
})
