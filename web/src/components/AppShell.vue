<script setup lang="ts">
/**
 * 卡 #27 (P2-S1):tabbed shell 作為應用外殼。
 * 改版 S2:header/shell 玻璃化(L3 toolbar)。
 *
 * header:brand「JimQ」+ nav [Live][Backtest][Research] 分頁籤(active = Apple 藍底
 * + 高光)+ mode badge(BACKTEST / LIVE-TESTNET)+ WS 連線狀態 glass pill + 全域
 * KILL 按鈕(危險高對比玻璃)。內容區 <RouterView/> 由 vue-router 切換。
 *
 * 換皮原則(契約):保留所有互動/store 綁定/data-testid 不變,只換外觀 →
 *   - brand/tabs/badge/連線狀態/KILL 行為與卡 #24/#27 一致;
 *   - header 改吃 theme.css token + GlassToolbar(L3),移除硬編色;
 *   - router-view 容器深色玻璃工作區(大面積背景禁 backdrop-filter,用實心 bg token)。
 */
import { inject } from 'vue'
import ConnectionStatus from '@/components/ConnectionStatus.vue'
import BackgroundPicker from '@/components/controls/BackgroundPicker.vue'
import { GlassToolbar } from '@/components/ui/glass'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
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
    <GlassToolbar as="header" class="shell-header">
      <div class="brand">JimQ</div>
      <nav class="tabs">
        <RouterLink to="/live" class="tab">Live</RouterLink>
        <RouterLink to="/backtest" class="tab">Backtest</RouterLink>
        <RouterLink to="/research" class="tab">Research</RouterLink>
      </nav>
      <div class="header-right">
        <Badge
          :variant="appMode.isLive ? 'default' : 'secondary'"
          :class="appMode.isLive ? 'badge-live' : ''"
          data-testid="mode-badge"
        >
          {{ appMode.badgeLabel }}
        </Badge>
        <ConnectionStatus />
        <BackgroundPicker />
        <Button
          variant="destructive"
          size="sm"
          class="kill"
          :disabled="control.pending.value"
          title="全域急停 — 停止所有策略 + 取消未成交單(對測試節點)"
          data-testid="kill-switch"
          @click="onKill"
        >
          KILL
        </Button>
      </div>
    </GlassToolbar>
    <main class="shell-body">
      <RouterView />
    </main>
  </div>
</template>

<style scoped>
.shell {
  display: flex;
  flex-direction: column;
  height: 100vh;
  /* 改版(背景切換):外殼透明,讓 html[data-bg]::before 的背景圖層透出,
     使玻璃面板(L1)的 blur/折射/高光顯現。大面積仍禁 backdrop-filter(契約)。 */
  background: transparent;
}

/* L3 玻璃 header 由 GlassToolbar 提供;此處只調間距/高度。 */
.shell-header {
  gap: calc(var(--spacing) * 5);
  padding: calc(var(--spacing) * 2) calc(var(--spacing) * 4);
}

.brand {
  font-weight: 700;
  color: var(--color-text);
  font-size: 15px;
  letter-spacing: 0.04em;
}

.tabs {
  display: flex;
  gap: var(--spacing);
}

/* 分頁籤:沿用 shadcn TabsTrigger 視覺語言(active = Apple 藍底 + 高光)。
   因導覽走 vue-router(RouterLink),故以 token CSS 還原同款外觀。 */
.tab {
  display: inline-flex;
  align-items: center;
  color: var(--color-text-muted);
  text-decoration: none;
  font-size: 13px;
  font-weight: 500;
  letter-spacing: -0.01em;
  padding: calc(var(--spacing) * 1.5) calc(var(--spacing) * 3);
  border-radius: var(--radius-sm);
  transition:
    background-color var(--duration-fast) var(--ease-glass),
    color var(--duration-fast) var(--ease-glass);
}

.tab:hover {
  color: var(--color-text);
  background: var(--surface-3);
}

.tab.router-link-active {
  color: #fff;
  font-weight: 600;
  background: var(--color-accent);
  box-shadow: var(--accent-glow);
}

.header-right {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: calc(var(--spacing) * 3);
}

/* LIVE-TESTNET：醒目藍底(default badge 已是 accent/15);此處加強對比讓即時模式一眼可見。 */
.badge-live {
  background: var(--color-accent);
  color: #fff;
  border-color: transparent;
  box-shadow: var(--accent-glow);
  letter-spacing: 0.05em;
  font-weight: 700;
}

/* KILL：危險高對比玻璃。destructive 變體已是跌色實心;此處強化字距/陰影。 */
.kill {
  letter-spacing: 0.05em;
  font-weight: 700;
}

/* 深色玻璃工作區:router-view 容器。透明讓背景圖層透出(玻璃面板在其上顯現)。 */
.shell-body {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  background: transparent;
}
</style>
