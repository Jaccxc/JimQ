<script setup lang="ts">
import { TabsTrigger, type TabsTriggerProps, useForwardProps } from 'reka-ui'
import { cn } from '@/lib/utils'

const props = defineProps<TabsTriggerProps & { class?: string }>()
const forwarded = useForwardProps(props)
</script>

<template>
  <TabsTrigger
    v-bind="forwarded"
    :class="
      cn(
        'inline-flex items-center justify-center whitespace-nowrap rounded-[var(--radius-xs)] px-3 py-1 text-sm font-medium transition-all duration-[var(--duration-fast)] ease-[var(--ease-glass)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent)] disabled:pointer-events-none disabled:opacity-50 data-[state=active]:bg-[var(--color-accent)] data-[state=active]:text-white data-[state=active]:shadow-[0_2px_8px_rgba(10,132,255,0.3)]',
        props.class,
      )
    "
  >
    <slot />
  </TabsTrigger>
</template>
