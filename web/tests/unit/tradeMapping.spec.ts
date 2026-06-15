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
  type PriceLineSpec,
} from '@/lib/tradeMapping'
import type { OrderFilledData, OrderInitializedData } from '@/types/contract'

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
