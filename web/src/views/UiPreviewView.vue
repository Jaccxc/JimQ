<script setup lang="ts">
/**
 * 改版 S1b — UI 元件預覽頁(/ui-preview)。
 * 展示 shadcn-vue 元件(button/card/dialog/select/tabs/tooltip/badge/table/input)
 * + 玻璃 primitives(GlassPanel/GlassToolbar/StatPill),供使用者視覺驗收。
 * 純展示頁,不接 store/API,不影響既有頁面。
 */
import { ref } from 'vue'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
} from '@/components/ui/card'
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from '@/components/ui/table'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import {
  Tooltip,
  TooltipProvider,
  TooltipTrigger,
  TooltipContent,
} from '@/components/ui/tooltip'
import {
  Dialog,
  DialogTrigger,
  DialogContent,
  DialogHeader,
  DialogFooter,
  DialogTitle,
  DialogDescription,
  DialogClose,
} from '@/components/ui/dialog'
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from '@/components/ui/select'
import { GlassPanel, GlassToolbar, StatPill } from '@/components/ui/glass'

const sample = ref('')
const fruit = ref('btc')

const rows = [
  { sym: 'BTC-USD', qty: 0.5, pnl: 1284.21 },
  { sym: 'ETH-USD', qty: 4, pnl: -312.05 },
  { sym: 'SOL-USD', qty: 120, pnl: 0 },
]
</script>

<template>
  <div class="preview-bg min-h-screen p-6">
    <header class="mx-auto mb-6 max-w-5xl">
      <h1 class="text-lg font-semibold tracking-[-0.01em] text-[var(--color-text)]">
        JimQ UI 預覽 — shadcn-vue + Glass primitives (改版 S1b)
      </h1>
      <p class="mt-1 text-sm text-[var(--color-text-muted)]">
        深色玻璃設計系統元件庫驗收頁。
      </p>
    </header>

    <main class="mx-auto grid max-w-5xl gap-6">
      <!-- Buttons + Badges -->
      <GlassPanel>
        <h2 class="mb-3 text-sm font-medium text-[var(--color-text-muted)]">
          Buttons / Badges
        </h2>
        <div class="flex flex-wrap items-center gap-3">
          <Button>Primary</Button>
          <Button variant="outline">Outline</Button>
          <Button variant="ghost">Ghost</Button>
          <Button variant="destructive">Kill</Button>
          <Button variant="link">Link</Button>
          <Button size="sm">Small</Button>
        </div>
        <div class="mt-3 flex flex-wrap items-center gap-2">
          <Badge>LIVE</Badge>
          <Badge variant="secondary">BACKTEST</Badge>
          <Badge variant="outline">RESEARCH</Badge>
          <Badge variant="up">+2.4%</Badge>
          <Badge variant="down">-1.1%</Badge>
        </div>
      </GlassPanel>

      <!-- StatPills -->
      <GlassPanel>
        <h2 class="mb-3 text-sm font-medium text-[var(--color-text-muted)]">
          StatPill (漲 / 跌 / 平)
        </h2>
        <div class="flex flex-wrap items-center gap-3">
          <StatPill :value="1284.21" signed />
          <StatPill :value="-312.05" :formatted="'-312.05'" />
          <StatPill :value="0" :formatted="'0.00'" />
        </div>
      </GlassPanel>

      <!-- Card + Input -->
      <Card>
        <CardHeader>
          <CardTitle>Card 元件</CardTitle>
          <CardDescription>L1 玻璃卡片 + Input。</CardDescription>
        </CardHeader>
        <CardContent class="flex flex-col gap-2">
          <label class="text-xs text-[var(--color-text-muted)]">下單數量</label>
          <Input v-model="sample" placeholder="0.00" />
          <p class="text-xs text-[var(--color-text-faint)]">輸入值:{{ sample || '—' }}</p>
        </CardContent>
        <CardFooter>
          <Button size="sm">送出</Button>
        </CardFooter>
      </Card>

      <!-- Tabs -->
      <GlassPanel>
        <h2 class="mb-3 text-sm font-medium text-[var(--color-text-muted)]">Tabs</h2>
        <Tabs default-value="positions">
          <TabsList>
            <TabsTrigger value="positions">Positions</TabsTrigger>
            <TabsTrigger value="orders">Orders</TabsTrigger>
            <TabsTrigger value="fills">Fills</TabsTrigger>
          </TabsList>
          <TabsContent value="positions">
            <p class="text-sm text-[var(--color-text-muted)]">持倉分頁內容。</p>
          </TabsContent>
          <TabsContent value="orders">
            <p class="text-sm text-[var(--color-text-muted)]">委託分頁內容。</p>
          </TabsContent>
          <TabsContent value="fills">
            <p class="text-sm text-[var(--color-text-muted)]">成交分頁內容。</p>
          </TabsContent>
        </Tabs>
      </GlassPanel>

      <!-- Table -->
      <GlassPanel :padded="false">
        <GlassToolbar class="rounded-t-[var(--radius-md)]">
          <span class="text-sm font-medium">Positions (GlassToolbar 表頭)</span>
          <div class="ml-auto">
            <Badge variant="secondary">3 rows</Badge>
          </div>
        </GlassToolbar>
        <div class="p-2">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Symbol</TableHead>
                <TableHead>Qty</TableHead>
                <TableHead>Unrealised PnL</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow v-for="r in rows" :key="r.sym">
                <TableCell>{{ r.sym }}</TableCell>
                <TableCell>{{ r.qty }}</TableCell>
                <TableCell>
                  <StatPill :value="r.pnl" :formatted="r.pnl.toFixed(2)" signed />
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </div>
      </GlassPanel>

      <!-- Select + Tooltip + Dialog -->
      <GlassPanel>
        <h2 class="mb-3 text-sm font-medium text-[var(--color-text-muted)]">
          Select / Tooltip / Dialog (L2 浮層)
        </h2>
        <div class="flex flex-wrap items-center gap-4">
          <div class="w-48">
            <Select v-model="fruit">
              <SelectTrigger>
                <SelectValue placeholder="選擇市場" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="btc">BTC-USD</SelectItem>
                <SelectItem value="eth">ETH-USD</SelectItem>
                <SelectItem value="sol">SOL-USD</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger as-child>
                <Button variant="outline">Hover 我</Button>
              </TooltipTrigger>
              <TooltipContent>玻璃 L2 tooltip</TooltipContent>
            </Tooltip>
          </TooltipProvider>

          <Dialog>
            <DialogTrigger as-child>
              <Button>開啟 Dialog</Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>確認動作</DialogTitle>
                <DialogDescription>
                  這是 L2 玻璃浮層 dialog,overlay 不上 blur(大面積壓暗)。
                </DialogDescription>
              </DialogHeader>
              <DialogFooter>
                <DialogClose as-child>
                  <Button variant="ghost">取消</Button>
                </DialogClose>
                <DialogClose as-child>
                  <Button variant="destructive">確認</Button>
                </DialogClose>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      </GlassPanel>
    </main>
  </div>
</template>

<style scoped>
/* 預覽頁底:大面積禁 backdrop-filter,用次層實心 bg + 一點漸層讓玻璃高光可見。 */
.preview-bg {
  background:
    radial-gradient(1200px 600px at 80% -10%, rgba(10, 132, 255, 0.12), transparent 60%),
    radial-gradient(900px 500px at 0% 110%, rgba(167, 139, 250, 0.1), transparent 60%),
    var(--color-bg);
}
</style>
