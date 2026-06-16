<script setup lang="ts">
import { SelectSeparator, type SelectSeparatorProps } from 'reka-ui'
import { cn } from '@/lib/utils'

const props = defineProps<SelectSeparatorProps & { class?: string }>()
</script>

<template>
  <SelectSeparator
    v-bind="props"
    :class="cn('-mx-1 my-1 h-px bg-[var(--glass-l1-border)]', props.class)"
  />
</template>
