<script setup lang="ts">
/**
 * 改版 S3 — 成交面板玻璃化(L1)。
 * 換皮:GlassPanel 外框 + shadcn table + tabular-nums + 買賣實心色。
 * 保留邏輯/store 綁定與 data-testid(fills-table)不變。
 */
import { useFillsStore } from '@/stores/fills'
import { GlassPanel } from '@/components/ui/glass'
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
  TableEmpty,
} from '@/components/ui/table'
const fills = useFillsStore()
</script>

<template>
  <GlassPanel class="panel" :padded="false">
    <h3 class="panel-title">成交 Fills</h3>
    <Table data-testid="fills-table">
      <TableHeader>
        <TableRow>
          <TableHead>Side</TableHead>
          <TableHead class="num">Qty</TableHead>
          <TableHead class="num">Px</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        <TableRow v-for="(f, i) in fills.fills.slice(-12).reverse()" :key="i">
          <TableCell :class="f.order_side === 'BUY' ? 'long' : 'short'">{{ f.order_side }}</TableCell>
          <TableCell class="num">{{ f.last_qty }}</TableCell>
          <TableCell class="num">{{ f.last_px }}</TableCell>
        </TableRow>
        <TableEmpty v-if="fills.fills.length === 0" :colspan="3">無成交</TableEmpty>
      </TableBody>
    </Table>
  </GlassPanel>
</template>

<style scoped>
.panel { overflow: hidden; }
.panel-title {
  margin: 0;
  padding: calc(var(--spacing) * 2.5) calc(var(--spacing) * 3);
  font-size: 12px;
  font-weight: 600;
  color: var(--color-text-muted);
  letter-spacing: -0.01em;
}
.num { text-align: right; font-variant-numeric: tabular-nums; }
.long { color: var(--color-up); font-weight: 600; }
.short { color: var(--color-down); font-weight: 600; }
</style>
