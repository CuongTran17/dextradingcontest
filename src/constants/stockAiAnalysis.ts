export type Decision = 'Strong Buy' | 'Buy' | 'Hold' | 'Sell' | 'Strong Sell'

export const POSITIVE_TOKENS = [
  'tang',
  'tich cuc',
  'vuot ke hoach',
  'mua',
  'breakout',
  'mo rong',
  'ky luc',
  'lai',
  'profit',
  'growth',
  'upgrade',
  'dividend',
  'co tuc',
]

export const NEGATIVE_TOKENS = [
  'giam',
  'rui ro',
  'ban',
  'ap luc',
  'thua lo',
  'dieu tra',
  'downgrade',
  'warning',
  'sell',
  'bearish',
  'suy yeu',
  'volatility spike',
]

export const DECISION_ORDER: Decision[] = ['Strong Buy', 'Buy', 'Hold', 'Sell', 'Strong Sell']

export const MODEL_LABELS = {
  primary: 'VN30 Analyst AI',
  ruleBased: 'VN30 Analyst AI (rule-based)',
} as const
