<script setup lang="ts">
import { cn } from '@/lib/utils'

const props = defineProps<{ class?: string }>()
</script>

<template>
  <p :class="cn('text-xs text-[var(--color-text-muted)]', props.class)">
    <slot />
  </p>
</template>
