/**
 * 行為測試:order/fill 事件 → Lightweight Charts marker / priceLine 映射(deep module)。
 *
 * 只驗 public interface 行為,不驗實作細節。
 * 真相來源:api/tests/test_nautilus_consumer.py 的實測 payload 形狀。
 */
import { describe, it, expect } from 'vitest'
import {
  fillToMarker,
  orderToPriceLines,
  tradeToMarkers,
  formatPrice,
  formatPnl,
  type PriceLineSpec,
} from '@/lib/tradeMapping'
import type { OrderFilledData, OrderInitializedData } from '@/types/contract'
import type { TradeRecord } from '@/api/trades'

const BUY_FILL: OrderFilledData = {
  type: 'OrderFilled',
  instrument_id: 'BTCUSDT-PERP.BINANCE',
  client_order_id: 'O-1',
  position_id: 'P-1',
  order_side: 'BUY',
  order_type: 'MARKET',
  last_qty: '0.100',
  last_px: '39960.0',
  ts_init: '1700000960000000000',
}

const SELL_FILL: OrderFilledData = {
  ...BUY_FILL,
  client_order_id: 'O-2',
  order_side: 'SELL',
  last_px: '40500.0',
  ts_init: '1700001020000000000',
}

describe('fillToMarker', () => {
  it('BUY fill → 向上箭頭(belowBar),time 為秒級', () => {
    const m = fillToMarker(BUY_FILL)
    expect(m.position).toBe('belowBar')
    expect(m.shape).toBe('arrowUp')
    // ts_init 奈秒 → 秒。
    expect(m.time).toBe(1700000960)
  })

  it('SELL fill → 向下箭頭(aboveBar)', () => {
    const m = fillToMarker(SELL_FILL)
    expect(m.position).toBe('aboveBar')
    expect(m.shape).toBe('arrowDown')
    expect(m.time).toBe(1700001020)
  })

  it('marker 帶 fill 價與量的文字標註', () => {
    const m = fillToMarker(BUY_FILL)
    expect(m.text).toContain('0.100')
    expect(m.text).toContain('39960')
  })
})

describe('orderToPriceLines', () => {
  it('STOP_MARKET(SL)→ 一條 SL priceLine,價取 trigger_price', () => {
    const sl: OrderInitializedData = {
      type: 'OrderInitialized',
      instrument_id: 'BTCUSDT-PERP.BINANCE',
      client_order_id: 'O-SL',
      order_side: 'SELL',
      order_type: 'STOP_MARKET',
      quantity: '0.100',
      trigger_price: '39000.0',
      ts_init: '1700000960000000000',
    }
    const lines: PriceLineSpec[] = orderToPriceLines(sl)
    expect(lines).toHaveLength(1)
    expect(lines[0].price).toBe(39000)
    expect(lines[0].kind).toBe('SL')
    expect(lines[0].title).toContain('SL')
  })

  it('LIMIT(TP)→ 一條 TP priceLine,價取 price', () => {
    const tp: OrderInitializedData = {
      type: 'OrderInitialized',
      instrument_id: 'BTCUSDT-PERP.BINANCE',
      client_order_id: 'O-TP',
      order_side: 'SELL',
      order_type: 'LIMIT',
      quantity: '0.100',
      price: '42000.0',
      ts_init: '1700000960000000000',
    }
    const lines = orderToPriceLines(tp)
    expect(lines).toHaveLength(1)
    expect(lines[0].price).toBe(42000)
    expect(lines[0].kind).toBe('TP')
  })

  it('MARKET 進場單(無 SL/TP 價)→ 無 priceLine', () => {
    const mkt: OrderInitializedData = {
      type: 'OrderInitialized',
      instrument_id: 'BTCUSDT-PERP.BINANCE',
      client_order_id: 'O-MKT',
      order_side: 'BUY',
      order_type: 'MARKET',
      quantity: '0.100',
      ts_init: '1700000960000000000',
    }
    expect(orderToPriceLines(mkt)).toHaveLength(0)
  })

  it('每條 priceLine 帶穩定 id(以 client_order_id 為基)便於後續移除', () => {
    const sl: OrderInitializedData = {
      type: 'OrderInitialized',
      instrument_id: 'BTCUSDT-PERP.BINANCE',
      client_order_id: 'O-SL',
      order_side: 'SELL',
      order_type: 'STOP_MARKET',
      quantity: '0.100',
      trigger_price: '39000.0',
      ts_init: '1700000960000000000',
    }
    expect(orderToPriceLines(sl)[0].id).toContain('O-SL')
  })
})

// --- 卡 D:進場 vs 出場 marker 視覺可區分 -----------------------------------
//
// round-trip trade 同時畫進場 + 出場兩 marker。過去兩者皆為箭頭、僅方向不同,
// 視覺上像「同一筆畫了兩次」。本卡要求進場與出場「形狀」與「顏色」皆不同,
// 並各帶可辨識的文字標(Entry / Exit)。

const LONG_TRADE: TradeRecord = {
  id: 7,
  run_id: 73,
  instrument_id: 'BTCUSDT-PERP.BINANCE',
  side: 'LONG',
  entry_price: '100',
  exit_price: '110',
  quantity: '0.5',
  sl: null,
  tp: null,
  pnl: '5',
  opened_at: '2024-01-01T00:00:00Z',
  closed_at: '2024-01-01T01:00:00Z',
}
const SHORT_TRADE: TradeRecord = {
  ...LONG_TRADE,
  id: 8,
  side: 'SHORT',
  entry_price: '110',
  exit_price: '100',
  pnl: '5',
}

describe('tradeToMarkers 進出場視覺區分', () => {
  it('回傳進場 + 出場兩個 marker', () => {
    expect(tradeToMarkers(LONG_TRADE)).toHaveLength(2)
  })

  it('進場與出場 marker 的形狀不同(非兩個一樣的箭頭)', () => {
    const [entry, exit] = tradeToMarkers(LONG_TRADE)
    expect(entry.shape).not.toBe(exit.shape)
  })

  it('進場與出場 marker 的顏色不同', () => {
    const [entry, exit] = tradeToMarkers(LONG_TRADE)
    expect(entry.color).not.toBe(exit.color)
  })

  it('進場 marker 文字含 Entry、出場 marker 文字含 Exit', () => {
    const [entry, exit] = tradeToMarkers(LONG_TRADE)
    expect(entry.text).toContain('Entry')
    expect(exit.text).toContain('Exit')
  })

  it('SHORT 進出場同樣形狀/顏色可區分', () => {
    const [entry, exit] = tradeToMarkers(SHORT_TRADE)
    expect(entry.shape).not.toBe(exit.shape)
    expect(entry.color).not.toBe(exit.color)
  })

  it('進場箭頭指向部位方向(LONG 向上、SHORT 向下);出場用非箭頭形狀', () => {
    const [longEntry] = tradeToMarkers(LONG_TRADE)
    expect(longEntry.shape).toBe('arrowUp')
    const [shortEntry, shortExit] = tradeToMarkers(SHORT_TRADE)
    expect(shortEntry.shape).toBe('arrowDown')
    // 出場形狀不是箭頭(circle/square),確保與進場箭頭視覺分離。
    expect(['arrowUp', 'arrowDown']).not.toContain(shortExit.shape)
  })
})

// --- 問題 1:進場/出場 marker 各顯示對應成交價,且與 PnL 號一致 ----------------
//
// 使用者回報 run #94「進出場 marker 同一價卻有非零 PnL」。實查 DB:同一筆 trade 的
// entry_price≠exit_price(差值 × qty × 方向 = pnl);只有 always-in-market 反手下
// 「某筆出場價 = 下一筆進場價」(同一根反手 fill),那是兩筆不同 trade 的邊界,
// 非同一筆。故 marker 取值正確的不變式:同一筆 entry/exit 文字標示不同價、且方向
// 與 pnl 號一致(進場 fixture 用 run #94 第 471 列:SHORT 42512.9→42532.3 pnl -1.94)。

const RUN94_LOSS_SHORT: TradeRecord = {
  id: 471,
  run_id: 94,
  instrument_id: 'BTCUSDT-PERP.BINANCE',
  side: 'SHORT',
  entry_price: '42512.90000000',
  exit_price: '42532.30000000',
  quantity: '0.10000000',
  sl: null,
  tp: null,
  pnl: '-1.94000000',
  opened_at: '2024-01-01T00:00:00Z',
  closed_at: '2024-01-01T00:02:00Z',
}

describe('tradeToMarkers 進出場各取對應成交價(問題1)', () => {
  it('同一筆的進場與出場 marker 標示不同價格', () => {
    const [entry, exit] = tradeToMarkers(RUN94_LOSS_SHORT)
    expect(entry.text).toContain('42512.9')
    expect(exit.text).toContain('42532.3')
    expect(entry.text).not.toBe(exit.text)
  })

  it('SHORT 虧損:進場價 < 出場價(價漲對空單不利,與負 PnL 一致)', () => {
    const [entry, exit] = tradeToMarkers(RUN94_LOSS_SHORT)
    expect(Number(RUN94_LOSS_SHORT.entry_price)).toBeLessThan(
      Number(RUN94_LOSS_SHORT.exit_price),
    )
    // 文字反映上述兩個不同價。
    expect(entry.text).toContain('Entry')
    expect(exit.text).toContain('Exit')
  })

  it('LONG 獲利:進場價 < 出場價(與正 PnL 一致),兩 marker 不同價', () => {
    const [entry, exit] = tradeToMarkers(LONG_TRADE) // 100 → 110, pnl 5
    expect(entry.text).toContain('100')
    expect(exit.text).toContain('110')
  })
})

// --- 問題 2:marker 文字去尾隨零 ------------------------------------------------

describe('formatPrice / formatPnl 去尾零', () => {
  it('formatPrice 去掉 NUMERIC 尾零', () => {
    expect(formatPrice('42532.30000000')).toBe('42532.3')
    expect(formatPrice('44472.50000000')).toBe('44472.5')
  })
  it('formatPrice 整數無小數點', () => {
    expect(formatPrice('42000.00000000')).toBe('42000')
  })
  it('formatPnl 兩位小數', () => {
    expect(formatPnl('-1.94000000')).toBe('-1.94')
    expect(formatPnl('5')).toBe('5.00')
  })
  it('formatPrice 非數字原樣回傳(防呆)', () => {
    expect(formatPrice('n/a')).toBe('n/a')
  })
})

describe('tradeToMarkers 文字無長尾零(問題2)', () => {
  it('出場文字為乾淨格式 Exit @ <price> (PnL <2dp>)', () => {
    const [, exit] = tradeToMarkers(RUN94_LOSS_SHORT)
    expect(exit.text).toBe('Exit @ 42532.3 (PnL -1.94)')
    // 無長尾零(連續 5 個以上的 0)。
    expect(exit.text).not.toMatch(/0{5,}/)
  })
  it('進場文字價格去尾零', () => {
    const [entry] = tradeToMarkers(RUN94_LOSS_SHORT)
    expect(entry.text).toContain('@ 42512.9')
    expect(entry.text).not.toMatch(/0{5,}/)
  })
})
