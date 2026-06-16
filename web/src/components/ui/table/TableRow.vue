<script setup lang="ts">
import { cn } from '@/lib/utils'

const props = defineProps<{ class?: string }>()
</script>

<template>
  <tr
    :class="
      cn(
        'border-b border-[var(--glass-l1-border)] transition-colors hover:bg-white/[0.03] data-[state=selected]:bg-white/[0.05]',
        props.class,
      )
    "
  >
    <slot />
  </tr>
</template>
