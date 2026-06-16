/**
 * 卡 #24 (W5) — 策略控制平面 store。
 *
 * 持有最近一次控制命令(供 UI 顯示狀態回饋)與全域 kill 旗標(header KILL 按下
 * 後反映)。狀態回流(策略真實 RUNNING/STOPPED)走既有 WS / 輪詢;此 store 只
 * 反映「已送出的控制意圖」。
 */
import { defineStore } from 'pinia'
import type { ControlAccepted } from '@/api/control'

interface State {
  lastCommand: ControlAccepted | null
  killed: boolean
}

export const useStrategyControlStore = defineStore('strategyControl', {
  state: (): State => ({
    lastCommand: null,
    killed: false,
  }),
  actions: {
    recordCommand(cmd: ControlAccepted) {
      this.lastCommand = cmd
      if (cmd.command_type === 'KILL') {
        this.killed = true
      }
    },
    reset() {
      this.killed = false
    },
  },
})
