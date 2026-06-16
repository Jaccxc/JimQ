<script setup lang="ts">
/**
 * 改版 S1b — StatPill:漲跌數字 pill。
 * 方向由 statSign(value) 衍生(正/負/0/NaN→up/down/flat);
 * 文字色用實心 --up/--down(不在玻璃上疊半透明色塊,契約),底用淡色 pill。
 * tabular-nums 對齊。可傳 formatted 覆寫顯示字串(否則直接顯示 value)。
 */
import { computed } from 'vue'
import { cn, statSign } from '@/lib/utils'

const props = defineProps<{
  value: number
  formatted?: string
  /** true 時正數加 + 前綴(PnL/變動量常用) */
  signed?: boolean
  class?: string
}>()

const direction = computed(() => statSign(props.value))

const display = computed(() => {
  if (props.formatted !== undefined) return props.formatted
  const v = props.value
  if (props.signed && Number.isFinite(v) && v > 0) return `+${v}`
  return String(v)
})

const toneClass = computed(() => {
  switch (direction.value) {
    case 'up':
      return 'text-[var(--color-up)] bg-[var(--color-up-pill)]'
    case 'down':
      return 'text-[var(--color-down)] bg-[var(--color-down-pill)]'
    default:
      return 'text-[var(--color-text-muted)] bg-white/[0.05]'
  }
})
</script>

<template>
  <span
    :data-direction="direction"
    :class="
      cn(
        'inline-flex items-center rounded-[var(--radius-xs)] px-2 py-0.5 text-xs font-medium tabular-nums',
        toneClass,
        props.class,
      )
    "
  >
    <slot>{{ display }}</slot>
  </span>
</template>
