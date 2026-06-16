/**
 * 卡 #21 (W2) — 行為測試:persisted trade(GET /backtests/{id}/trades 的列)
 * → 進出場 marker + SL/TP priceLine 映射(deep module),供重載歷史 K 線時畫
 * 該次 backtest 的進出場。
 *
 * 只驗 public interface 行為。trade 形狀對齊 api BacktestTradeRead。
 */
import { describe, it, expect } from 'vitest'
import { tradeToMarkers, tradeToPriceLines } from '@/lib/tradeMapping'
import type { TradeRecord } from '@/api/trades'

const LONG_TRADE: TradeRecord = {
  id: 1,
  run_id: 42,
  instrument_id: 'BTCUSDT-PERP.BINANCE',
  side: 'LONG',
  entry_price: '37000.5',
  exit_price: '37500.25',
  quantity: '0.5',
  sl: '36630.0',
  tp: '37740.0',
  pnl: '249.875',
  // 2024-01-01T00:00:00Z = 1704067200 ; +1h = 1704070800
  opened_at: '2024-01-01T00:00:00Z',
  closed_at: '2024-01-01T01:00:00Z',
}

const SHORT_NO_BRACKET: TradeRecord = {
  ...LONG_TRADE,
  id: 2,
  side: 'SHORT',
  sl: null,
  tp: null,
}

describe('tradeToMarkers', () => {
  it('一筆成交 → 進場 + 出場兩個 marker', () => {
    const m = tradeToMarkers(LONG_TRADE)
    expect(m).toHaveLength(2)
  })

  it('LONG:進場向上箭頭(belowBar)於 opened_at,出場向下箭頭(aboveBar)於 closed_at', () => {
    const [entry, exit] = tradeToMarkers(LONG_TRADE)
    expect(entry.shape).toBe('arrowUp')
    expect(entry.position).toBe('belowBar')
    expect(entry.time).toBe(1704067200)
    expect(exit.shape).toBe('arrowDown')
    expect(exit.position).toBe('aboveBar')
    expect(exit.time).toBe(1704070800)
  })

  it('SHORT:進場向下箭頭,出場向上箭頭', () => {
    const [entry, exit] = tradeToMarkers(SHORT_NO_BRACKET)
    expect(entry.shape).toBe('arrowDown')
    expect(exit.shape).toBe('arrowUp')
  })

  it('進場 marker 文字含方向與進場價', () => {
    const [entry] = tradeToMarkers(LONG_TRADE)
    expect(entry.text).toContain('LONG')
    expect(entry.text).toContain('37000.5')
  })
})

describe('tradeToPriceLines', () => {
  it('有 SL/TP → 兩條 priceLine(SL + TP),價取自欄位', () => {
    const lines = tradeToPriceLines(LONG_TRADE)
    const kinds = lines.map((l) => l.kind).sort()
    expect(kinds).toEqual(['SL', 'TP'])
    const sl = lines.find((l) => l.kind === 'SL')!
    const tp = lines.find((l) => l.kind === 'TP')!
    expect(sl.price).toBe(36630)
    expect(tp.price).toBe(37740)
  })

  it('priceLine id 以 trade id 為基(便於重載時去重/移除)', () => {
    const lines = tradeToPriceLines(LONG_TRADE)
    expect(lines.every((l) => l.id.includes('1'))).toBe(true)
  })

  it('無 SL/TP → 無 priceLine', () => {
    expect(tradeToPriceLines(SHORT_NO_BRACKET)).toHaveLength(0)
  })
})
