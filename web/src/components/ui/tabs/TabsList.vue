<script setup lang="ts">
import { TabsList, type TabsListProps } from 'reka-ui'
import { cn } from '@/lib/utils'

const props = defineProps<TabsListProps & { class?: string }>()
</script>

<template>
  <TabsList
    v-bind="props"
    :class="
      cn(
        'inline-flex h-9 items-center justify-center gap-1 rounded-[var(--radius-sm)] border border-[var(--glass-l1-border)] bg-white/[0.03] p-1 text-[var(--color-text-muted)]',
        props.class,
      )
    "
  >
    <slot />
  </TabsList>
</template>
