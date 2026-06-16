<script setup lang="ts">
import { TabsContent, type TabsContentProps } from 'reka-ui'
import { cn } from '@/lib/utils'

const props = defineProps<TabsContentProps & { class?: string }>()
</script>

<template>
  <TabsContent
    v-bind="props"
    :class="
      cn(
        'mt-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent)]',
        props.class,
      )
    "
  >
    <slot />
  </TabsContent>
</template>
