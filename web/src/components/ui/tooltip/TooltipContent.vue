<script setup lang="ts">
import {
  TooltipContent,
  type TooltipContentEmits,
  type TooltipContentProps,
  TooltipPortal,
  useForwardPropsEmits,
} from 'reka-ui'
import { cn } from '@/lib/utils'

defineOptions({ inheritAttrs: false })

const props = withDefaults(
  defineProps<TooltipContentProps & { class?: string }>(),
  { sideOffset: 6 },
)
const emits = defineEmits<TooltipContentEmits>()

const forwarded = useForwardPropsEmits(props, emits)
</script>

<template>
  <TooltipPortal>
    <TooltipContent
      v-bind="{ ...forwarded, ...$attrs }"
      :class="
        cn(
          'glass-l2 z-50 overflow-hidden px-2.5 py-1.5 text-xs text-[var(--color-text)] shadow-[var(--glass-l1-shadow)] data-[state=delayed-open]:animate-in data-[state=closed]:animate-out',
          props.class,
        )
      "
    >
      <slot />
    </TooltipContent>
  </TooltipPortal>
</template>
