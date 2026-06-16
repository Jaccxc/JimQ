<script setup lang="ts">
/**
 * 改版 S1b — GlassToolbar:L3 header/控制列 primitive。
 * 用 theme.css 的 .glass-l3(blur 12px + 底部分隔線 + 頂部高光)。
 * 給 header / 控制列 / 過濾列;預設 flex 排版 + 內距。
 */
import { Primitive, type PrimitiveProps } from 'reka-ui'
import { cn } from '@/lib/utils'

const props = withDefaults(
  defineProps<PrimitiveProps & { class?: string }>(),
  { as: 'div' },
)
</script>

<template>
  <Primitive
    :as="props.as"
    :as-child="props.asChild"
    :class="
      cn(
        'glass-l3 flex items-center gap-3 px-4 py-2 text-[var(--color-text)]',
        props.class,
      )
    "
  >
    <slot />
  </Primitive>
</template>
