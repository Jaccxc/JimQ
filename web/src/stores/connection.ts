/**
 * 連線 store:WS 連線狀態 + last_seq(補洞游標)+ 重連次數。
 *
 * lastSeq 單調不回退(取最大),供重連時帶 last_seq query 補洞。
 */
import { defineStore } from 'pinia'

export type ConnStatus = 'disconnected' | 'connecting' | 'connected' | 'live'

interface State {
  status: ConnStatus
  lastSeq: number
  reconnectAttempts: number
  lastHeartbeat: number | null
}

export const useConnectionStore = defineStore('connection', {
  state: (): State => ({
    status: 'disconnected',
    lastSeq: 0,
    reconnectAttempts: 0,
    lastHeartbeat: null,
  }),
  actions: {
    setStatus(s: ConnStatus) {
      this.status = s
    },
    /** 觀察到一個 seq;單調取最大(補洞/快照亂序也安全)。 */
    observeSeq(seq: number) {
      if (seq > this.lastSeq) this.lastSeq = seq
    },
    incReconnect() {
      this.reconnectAttempts += 1
    },
    resetReconnect() {
      this.reconnectAttempts = 0
    },
    markHeartbeat(ts: number) {
      this.lastHeartbeat = ts
    },
  },
})
