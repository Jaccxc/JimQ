<script setup lang="ts">
/**
 * 改版 S1b — GlassPanel:L1 玻璃面板 primitive。
 * 用 theme.css 的 .glass-l1(blur 16px + saturate 150% + 頂部高光 + shadow)。
 * 卡片層級可用 backdrop-filter(大面積背景另由頁面用實心 bg,契約)。
 * 可選 padding 預設;as 允許切換語意標籤(section/article)。
 */
import { Primitive, type PrimitiveProps } from 'reka-ui'
import { cn } from '@/lib/utils'

const props = withDefaults(
  defineProps<PrimitiveProps & { class?: string; padded?: boolean }>(),
  { as: 'section', padded: true },
)
</script>

<template>
  <Primitive
    :as="props.as"
    :as-child="props.asChild"
    :class="
      cn(
        'glass-l1 text-[var(--color-text)]',
        props.padded && 'p-4',
        props.class,
      )
    "
  >
    <slot />
  </Primitive>
</template>
