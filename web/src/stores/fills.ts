/**
 * 成交 store:累積 OrderFilled 事件(供 panel + marker 驅動)。
 */
import { defineStore } from 'pinia'
import type { OrderFilledData } from '@/types/contract'

const MAX = 500

interface State {
  fills: OrderFilledData[]
}

export const useFillsStore = defineStore('fills', {
  state: (): State => ({ fills: [] }),
  actions: {
    add(f: OrderFilledData) {
      this.fills.push(f)
      if (this.fills.length > MAX) this.fills.splice(0, this.fills.length - MAX)
    },
  },
})
