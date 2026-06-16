<script setup lang="ts">
import { computed } from 'vue'
import { cn } from '@/lib/utils'

const props = defineProps<{
  modelValue?: string | number
  class?: string
}>()

const emits = defineEmits<{
  (e: 'update:modelValue', payload: string | number): void
}>()

const model = computed({
  get: () => props.modelValue ?? '',
  set: (v: string | number) => emits('update:modelValue', v),
})
</script>

<template>
  <input
    v-model="model"
    :class="
      cn(
        'flex h-9 w-full rounded-[var(--radius-sm)] border border-[var(--glass-l1-border)] bg-white/[0.03] px-3 py-1 text-sm text-[var(--color-text)] tabular-nums shadow-sm transition-colors placeholder:text-[var(--color-text-faint)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent)] focus-visible:border-transparent disabled:cursor-not-allowed disabled:opacity-50',
        props.class,
      )
    "
  />
</template>
