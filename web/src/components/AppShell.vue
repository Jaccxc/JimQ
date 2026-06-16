<script setup lang="ts">
/**
 * 卡 #27 (P2-S1) — tabbed shell(已拍板 IA)。
 *
 * header:nav [Live][Backtest][Research] 分頁籤 + mode badge(BACKTEST /
 * LIVE-TESTNET)+ 全域 KILL 按鈕(本卡 placeholder/disabled,真功能待 P2-S3)
 * + WS 連線狀態。內容區 <RouterView/> 由 vue-router 切換。
 */
import { inject } from 'vue'
import ConnectionStatus from '@/components/ConnectionStatus.vue'
import { useAppModeStore } from '@/stores/appMode'
import { useStrategyControl, type ControlApi } from '@/composables/useStrategyControl'

const appMode = useAppModeStore()

// 卡 #24 (W5):全域 KILL 接命令平面。可注入 control api(測試決定論);
// 預設用真實 REST client。
const injectedApi = inject<Partial<ControlApi> | undefined>('strategyControlApi', undefined)
const control = useStrategyControl({ api: injectedApi })

async function onKill() {
  await control.kill()
}
</script>

<template>
  <div class="shell">
    <header class="shell-header">
      <div class="brand">JimQ</div>
      <nav class="tabs">
        <RouterLink to="/live" class="tab">Live</RouterLink>
        <RouterLink to="/backtest" class="tab">Backtest</RouterLink>
        <RouterLink to="/research" class="tab">Research</RouterLink>
      </nav>
      <div class="header-right">
        <span
          class="mode-badge"
          :class="appMode.isLive ? 'badge-live' : 'badge-backtest'"
          data-testid="mode-badge"
        >
          {{ appMode.badgeLabel }}
        </span>
        <ConnectionStatus />
        <button
          class="kill"
          type="button"
          :disabled="control.pending.value"
          title="全域急停 — 停止所有策略 + 取消未成交單(對測試節點)"
          data-testid="kill-switch"
          @click="onKill"
        >
          KILL
        </button>
      </div>
    </header>
    <main class="shell-body">
      <RouterView />
    </main>
  </div>
</template>

<style scoped>
.shell { display: flex; flex-direction: column; height: 100vh; background: #0e1117; }
.shell-header {
  display: flex; align-items: center; gap: 20px;
  padding: 6px 14px; background: #11151d; border-bottom: 1px solid #1c2230;
}
.brand { font-weight: 700; color: #e5e7eb; font-size: 14px; letter-spacing: 0.04em; }
.tabs { display: flex; gap: 4px; }
.tab {
  color: #9ca3af; text-decoration: none; font-size: 13px;
  padding: 6px 12px; border-radius: 6px;
}
.tab:hover { color: #d1d4dc; background: #181d28; }
.tab.router-link-active { color: #e5e7eb; font-weight: 600; background: #1c2230; }
.header-right { margin-left: auto; display: flex; align-items: center; gap: 14px; }
.mode-badge {
  font-size: 11px; font-weight: 700; letter-spacing: 0.05em;
  padding: 3px 8px; border-radius: 4px; text-transform: uppercase;
}
.badge-backtest { background: #1f2937; color: #93c5fd; border: 1px solid #334155; }
.badge-live { background: #422006; color: #fbbf24; border: 1px solid #b45309; }
.kill {
  font-size: 11px; font-weight: 700; letter-spacing: 0.05em;
  padding: 4px 10px; border-radius: 4px;
  background: #3f1d1d; color: #f87171; border: 1px solid #7f1d1d;
  cursor: pointer;
}
.kill:hover:not(:disabled) { background: #7f1d1d; color: #fecaca; }
.kill:disabled { cursor: not-allowed; opacity: 0.6; }
.shell-body { flex: 1; min-height: 0; overflow: hidden; }
</style>
