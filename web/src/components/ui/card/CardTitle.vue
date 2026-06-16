<script setup lang="ts">
import { cn } from '@/lib/utils'

const props = defineProps<{ class?: string }>()
</script>

<template>
  <h3
    :class="
      cn(
        'text-sm font-semibold leading-none tracking-[-0.01em] text-[var(--color-text)]',
        props.class,
      )
    "
  >
    <slot />
  </h3>
</template>
