/**
 * 卡 #24 (W5) — 策略控制平面 composable。
 *
 * 串接 control store 與 REST:
 * - start(id, params):啟動策略(POST /strategies/{id}/start)。
 * - stop(id):停止策略(POST /strategies/{id}/stop)。
 * - kill():全域急停(POST /kill)→ 停止所有策略 + 取消未成交單。
 *
 * 每個動作成功後把回應記到 store(供 UI 狀態回饋);失敗記到 error(不拋,讓
 * UI 顯示)。api 以參數注入(預設真實 client),測試可注入 fake 達決定論。
 */
import { ref } from 'vue'
import {
  startStrategy as realStart,
  stopStrategy as realStop,
  killAll as realKill,
  type ControlAccepted,
} from '@/api/control'
import { useStrategyControlStore } from '@/stores/strategyControl'

/** 注入點:REST client(預設真實)。 */
export interface ControlApi {
  startStrategy: (id: string, params: Record<string, unknown>) => Promise<ControlAccepted>
  stopStrategy: (id: string) => Promise<ControlAccepted>
  killAll: () => Promise<ControlAccepted>
}

export interface UseStrategyControlOptions {
  api?: Partial<ControlApi>
}

export function useStrategyControl(opts: UseStrategyControlOptions = {}) {
  const api: ControlApi = {
    startStrategy: opts.api?.startStrategy ?? ((id, params) => realStart(id, params)),
    stopStrategy: opts.api?.stopStrategy ?? ((id) => realStop(id)),
    killAll: opts.api?.killAll ?? (() => realKill()),
  }
  const store = useStrategyControlStore()
  const pending = ref(false)
  const error = ref<string | null>(null)

  async function run(action: () => Promise<ControlAccepted>): Promise<void> {
    pending.value = true
    error.value = null
    try {
      store.recordCommand(await action())
    } catch (e) {
      error.value = (e as Error).message
    } finally {
      pending.value = false
    }
  }

  async function start(id: string, params: Record<string, unknown> = {}): Promise<void> {
    await run(() => api.startStrategy(id, params))
  }

  async function stop(id: string): Promise<void> {
    await run(() => api.stopStrategy(id))
  }

  async function kill(): Promise<void> {
    await run(() => api.killAll())
  }

  return { store, pending, error, start, stop, kill }
}
