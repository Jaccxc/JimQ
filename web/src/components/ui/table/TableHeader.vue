<script setup lang="ts">
import { cn } from '@/lib/utils'

const props = defineProps<{ class?: string }>()
</script>

<template>
  <thead :class="cn('[&_tr]:border-b [&_tr]:border-[var(--glass-l1-border)]', props.class)">
    <slot />
  </thead>
</template>
