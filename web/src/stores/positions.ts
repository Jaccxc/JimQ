/**
 * 部位 store:以 position_id upsert;FLAT(平倉)移除。
 *
 * scope 命名空間:`usePositionsStore('live'|'backtest')` 各拿獨立 state
 * (`defineStore('positions:'+scope)`,Map memoize)。預設 scope='live' 相容。
 */
import { defineStore } from 'pinia'
import type { PositionData } from '@/types/contract'

interface State {
  byId: Record<string, PositionData>
}

function definePositionsStore(scope: string) {
  return defineStore(`positions:${scope}`, {
      state: (): State => ({ byId: {} }),
      getters: {
        positions: (s): PositionData[] => Object.values(s.byId),
      },
      actions: {
        upsert(p: PositionData) {
          if (p.side === 'FLAT') {
            delete this.byId[p.position_id]
          } else {
            this.byId[p.position_id] = p
          }
        },
      },
    })
}

const cache = new Map<string, ReturnType<typeof definePositionsStore>>()

export function usePositionsStore(scope = 'live') {
  let def = cache.get(scope)
  if (!def) {
    def = definePositionsStore(scope)
    cache.set(scope, def)
  }
  return def()
}
