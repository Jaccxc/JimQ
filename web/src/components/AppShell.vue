<script setup lang="ts">
/**
 * 卡 #27 (P2-S1) — tabbed shell(已拍板 IA)。
 *
 * header:nav [Live][Backtest][Research] 分頁籤 + mode badge(BACKTEST /
 * LIVE-TESTNET)+ 全域 KILL 按鈕(本卡 placeholder/disabled,真功能待 P2-S3)
 * + WS 連線狀態。內容區 <RouterView/> 由 vue-router 切換。
 */
import ConnectionStatus from '@/components/ConnectionStatus.vue'
import { useAppModeStore } from '@/stores/appMode'

const appMode = useAppModeStore()
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
          disabled
          title="全域急停 — 真功能待 P2-S3"
          data-testid="kill-switch"
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
  cursor: not-allowed; opacity: 0.6;
}
.shell-body { flex: 1; min-height: 0; overflow: hidden; }
</style>
