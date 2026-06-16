/**
 * WS 信封分派器(純邏輯,可測):把一則 WsMessage 路由到對應 Pinia store
 * 並更新 connection 狀態。useTradeSocket 的 onmessage 直接呼叫這裡。
 *
 * 對齊 gateway 信封流(api/src/app/ws/stream.py):
 * - 補洞 / 快照(snapshot:true)/ delta 都是 {channel, seq, data} → 照 channel 分派,
 *   每筆都 observeSeq(更新 last_seq 補洞游標)。
 * - {type:"live"} → 標記進入即時串流。
 * - {type:"heartbeat"} → 記錄心跳。
 */
import {
  isEnvelope,
  isHeartbeat,
  isLiveMarker,
  type WsMessage,
  type BarDTO,
  type TradeData,
  type PositionData,
  type OrderInitializedData,
  type OrderFilledData,
  type AccountStateData,
} from '@/types/contract'
import { useMarketStore } from '@/stores/market'
import { usePositionsStore } from '@/stores/positions'
import { useOrdersStore } from '@/stores/orders'
import { useFillsStore } from '@/stores/fills'
import { usePnlStore } from '@/stores/pnl'
import { useConnectionStore } from '@/stores/connection'

/**
 * 把一則信封路由到**對應 scope 命名空間**的 stores(真 bug 修復)。
 *
 * scope 預設 'live'(相容):Live 分頁 socket(scope=live)→ live 命名空間;
 * Backtest 分頁 socket(scope=backtest)→ backtest 命名空間。兩者讀寫不同 store
 * 實例 → Live 圖/面板不會看到 backtest 的 bars/marks/部位/PnL/成交,反之亦然。
 *
 * connection store 維持**全域單一**:它只承載 WS 連線狀態 + last_seq 補洞游標
 * (header 顯示用),非串流交易 state;兩個 socket 各自更新無語意衝突。
 */
export function dispatchMessage(msg: WsMessage, scope = 'live'): void {
  const conn = useConnectionStore()

  if (isLiveMarker(msg)) {
    conn.setStatus('live')
    return
  }
  if (isHeartbeat(msg)) {
    conn.markHeartbeat(msg.ts)
    return
  }
  if (!isEnvelope(msg)) return

  conn.observeSeq(msg.seq)
  const data = msg.data

  switch (msg.channel) {
    case 'bars':
      useMarketStore(scope).applyBar(data as unknown as BarDTO)
      break
    case 'trades': {
      // 卡 B:逐筆成交 → 聚合到形成中那根 1m K 線(⛔ 純視覺,不碰交易 stores)。
      const t = data as unknown as TradeData
      useMarketStore(scope).applyTick({ time: t.time, price: t.price })
      break
    }
    case 'positions':
      usePositionsStore(scope).upsert(data as unknown as PositionData)
      break
    case 'orders':
      useOrdersStore(scope).add(data as unknown as OrderInitializedData)
      break
    case 'fills':
      useFillsStore(scope).add(data as unknown as OrderFilledData)
      break
    case 'pnl':
      usePnlStore(scope).set(data as unknown as AccountStateData)
      break
  }
}
