<script setup lang="ts">
import { cn } from '@/lib/utils'

const props = defineProps<{ class?: string; colspan?: number }>()
</script>

<template>
  <tr>
    <td
      :colspan="props.colspan ?? 1"
      :class="cn('p-6 text-center text-sm text-[var(--color-text-muted)]', props.class)"
    >
      <slot />
    </td>
  </tr>
</template>
