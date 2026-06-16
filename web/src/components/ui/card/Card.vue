<script setup lang="ts">
import { cn } from '@/lib/utils'

const props = defineProps<{ class?: string }>()
</script>

<template>
  <!-- Card = L1 玻璃面板。大面積背景禁 backdrop-filter,Card 屬卡片層級可用。 -->
  <div
    :class="
      cn(
        'glass-l1 text-[var(--color-text)]',
        props.class,
      )
    "
  >
    <slot />
  </div>
</template>
