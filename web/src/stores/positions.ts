/**
 * 部位 store:以 position_id upsert;FLAT(平倉)移除。
 */
import { defineStore } from 'pinia'
import type { PositionData } from '@/types/contract'

interface State {
  byId: Record<string, PositionData>
}

export const usePositionsStore = defineStore('positions', {
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
