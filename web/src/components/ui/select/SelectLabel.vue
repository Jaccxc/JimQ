<script setup lang="ts">
import { SelectLabel, type SelectLabelProps } from 'reka-ui'
import { cn } from '@/lib/utils'

const props = defineProps<SelectLabelProps & { class?: string }>()
</script>

<template>
  <SelectLabel
    v-bind="props"
    :class="cn('px-2 py-1.5 text-xs text-[var(--color-text-muted)]', props.class)"
  >
    <slot />
  </SelectLabel>
</template>
