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

export function dispatchMessage(msg: WsMessage): void {
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
      useMarketStore().applyBar(data as unknown as BarDTO)
      break
    case 'positions':
      usePositionsStore().upsert(data as unknown as PositionData)
      break
    case 'orders':
      useOrdersStore().add(data as unknown as OrderInitializedData)
      break
    case 'fills':
      useFillsStore().add(data as unknown as OrderFilledData)
      break
    case 'pnl':
      usePnlStore().set(data as unknown as AccountStateData)
      break
  }
}
