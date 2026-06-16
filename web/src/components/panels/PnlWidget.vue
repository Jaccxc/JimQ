<script setup lang="ts">
/**
 * 改版 S3 — 權益 PnL 面板玻璃化(L1)。
 * 換皮:GlassPanel 外框 + 大號 tabular-nums 權益數字。
 * 保留邏輯/store 綁定與 data-testid(pnl-widget)不變。
 */
import { usePnlStore } from '@/stores/pnl'
import { GlassPanel } from '@/components/ui/glass'
const pnl = usePnlStore()
</script>

<template>
  <GlassPanel class="panel pnl" data-testid="pnl-widget">
    <h3 class="panel-title">權益 PnL</h3>
    <div class="equity">
      <span v-if="pnl.equity != null" class="value">{{ pnl.equity.toLocaleString() }}</span>
      <span v-else class="empty">—</span>
      <small v-if="pnl.latest" class="ccy"> {{ pnl.latest.base_currency }}</small>
    </div>
  </GlassPanel>
</template>

<style scoped>
.panel-title {
  margin: 0 0 calc(var(--spacing) * 2);
  font-size: 12px;
  font-weight: 600;
  color: var(--color-text-muted);
  letter-spacing: -0.01em;
}
.equity {
  display: flex;
  align-items: baseline;
  gap: calc(var(--spacing) * 1.5);
}
.value {
  font-size: 26px;
  font-weight: 700;
  color: var(--color-text);
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.02em;
}
.ccy { font-size: 12px; color: var(--color-text-muted); }
.empty { font-size: 26px; font-weight: 700; color: var(--color-text-faint); }
</style>
