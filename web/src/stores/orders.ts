/**
 * 委託 store:累積 OrderInitialized 事件(供 panel + priceLine 驅動)。
 */
import { defineStore } from 'pinia'
import type { OrderInitializedData } from '@/types/contract'

const MAX = 500

interface State {
  orders: OrderInitializedData[]
}

export const useOrdersStore = defineStore('orders', {
  state: (): State => ({ orders: [] }),
  actions: {
    add(o: OrderInitializedData) {
      this.orders.push(o)
      if (this.orders.length > MAX) this.orders.splice(0, this.orders.length - MAX)
    },
  },
})
