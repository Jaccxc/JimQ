<script setup lang="ts">
import { DialogTitle, type DialogTitleProps } from 'reka-ui'
import { cn } from '@/lib/utils'

const props = defineProps<DialogTitleProps & { class?: string }>()
</script>

<template>
  <DialogTitle
    v-bind="props"
    :class="
      cn('text-base font-semibold tracking-[-0.01em] text-[var(--color-text)]', props.class)
    "
  >
    <slot />
  </DialogTitle>
</template>
