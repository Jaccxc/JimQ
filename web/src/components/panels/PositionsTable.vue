<script setup lang="ts">
/**
 * 改版 S3 — 部位面板玻璃化(L1)。
 * 換皮:GlassPanel 外框 + shadcn table + tabular-nums + 漲跌實心色。
 * 保留邏輯/store 綁定與 data-testid(positions-table)不變。
 */
import { usePositionsStore } from '@/stores/positions'
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
const positions = usePositionsStore()
</script>

<template>
  <GlassPanel class="panel" :padded="false">
    <h3 class="panel-title">部位 Positions</h3>
    <Table data-testid="positions-table">
      <TableHeader>
        <TableRow>
          <TableHead>ID</TableHead>
          <TableHead>Side</TableHead>
          <TableHead class="num">Qty</TableHead>
          <TableHead class="num">Avg Px</TableHead>
          <TableHead class="num">Last Px</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        <TableRow v-for="p in positions.positions" :key="p.position_id">
          <TableCell class="id">{{ p.position_id }}</TableCell>
          <TableCell :class="p.side === 'LONG' ? 'long' : 'short'">{{ p.side }}</TableCell>
          <TableCell class="num">{{ p.quantity }}</TableCell>
          <TableCell class="num">{{ p.avg_px_open }}</TableCell>
          <TableCell class="num">{{ p.last_px }}</TableCell>
        </TableRow>
        <TableEmpty v-if="positions.positions.length === 0" :colspan="5">無持倉</TableEmpty>
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
.id { color: var(--color-text-faint); font-variant-numeric: tabular-nums; }
.long { color: var(--color-up); font-weight: 600; }
.short { color: var(--color-down); font-weight: 600; }
</style>
