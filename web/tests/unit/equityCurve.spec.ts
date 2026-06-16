/**
 * 卡 C — 行為測試:tradesToEquityCurve(persisted trades → 累積權益曲線)。
 *
 * Backtest 主圖下方的 PnL/權益副圖資料源:把某 run 的 round-trip trades 依
 * 出場時間排序後,逐筆累加已實現 PnL,輸出與 LWC LineSeries 對齊的點
 * ({ time, value }),時間用出場時間(closed_at)epoch 秒,value 為累積權益。
 *
 * 純函式 deep module,只驗 public interface 行為(不驗實作細節)。
 */
import { describe, it, expect } from 'vitest'
import { tradesToEquityCurve } from '@/lib/equityCurve'
import type { TradeRecord } from '@/api/trades'

const base: Omit<TradeRecord, 'id' | 'pnl' | 'opened_at' | 'closed_at'> = {
  run_id: 1,
  instrument_id: 'BTCUSDT-PERP.BINANCE',
  side: 'LONG',
  entry_price: '100',
  exit_price: '110',
  quantity: '1',
  sl: null,
  tp: null,
}

function trade(id: number, pnl: string | null, closedAt: string): TradeRecord {
  return {
    ...base,
    id,
    pnl,
    opened_at: closedAt,
    closed_at: closedAt,
  }
}

describe('tradesToEquityCurve', () => {
  it('空 trades → 空曲線', () => {
    expect(tradesToEquityCurve([])).toEqual([])
  })

  it('逐筆累加已實現 PnL(value = 至此累積權益)', () => {
    // 2024-01-01T00:00:00Z=1704067200 ; +1h=1704070800 ; +2h=1704074400
    const curve = tradesToEquityCurve([
      trade(1, '100', '2024-01-01T00:00:00Z'),
      trade(2, '-30', '2024-01-01T01:00:00Z'),
      trade(3, '50', '2024-01-01T02:00:00Z'),
    ])
    expect(curve).toEqual([
      { time: 1704067200, value: 100 },
      { time: 1704070800, value: 70 },
      { time: 1704074400, value: 120 },
    ])
  })

  it('依出場時間(closed_at)排序後累加,輸入亂序也正確', () => {
    const curve = tradesToEquityCurve([
      trade(2, '-30', '2024-01-01T01:00:00Z'),
      trade(1, '100', '2024-01-01T00:00:00Z'),
    ])
    // 排序後先 100,再 -30 → 70。
    expect(curve.map((p) => p.value)).toEqual([100, 70])
    expect(curve[0].time).toBe(1704067200)
  })

  it('pnl 為 null 的 trade 視為 0 貢獻(權益不變但仍產生一個點)', () => {
    const curve = tradesToEquityCurve([
      trade(1, '40', '2024-01-01T00:00:00Z'),
      trade(2, null, '2024-01-01T01:00:00Z'),
    ])
    expect(curve.map((p) => p.value)).toEqual([40, 40])
  })

  it('可選 startingEquity:曲線從起始權益累加', () => {
    const curve = tradesToEquityCurve(
      [trade(1, '40', '2024-01-01T00:00:00Z')],
      1000,
    )
    expect(curve[0].value).toBe(1040)
  })
})
