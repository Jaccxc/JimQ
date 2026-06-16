<script setup lang="ts">
/**
 * 外觀/背景選擇器(header)。
 *
 * 點開 popover 列出 5 種背景設計(色票縮圖 + 標籤 + 描述),點選即時套用 + persist。
 * 真相來源 = stores/appearance(current / setBackground)。背景樣式在 backgrounds.css。
 *
 * data-testid:
 *   - bg-picker-trigger:開關按鈕
 *   - bg-option-<id>:每個選項
 */
import { ref } from 'vue'
import { Popover, PopoverTrigger, PopoverContent } from '@/components/ui/popover'
import { useAppearanceStore, BACKGROUNDS } from '@/stores/appearance'

const appearance = useAppearanceStore()
const open = ref(false)

function choose(id: string) {
  appearance.setBackground(id)
  open.value = false
}
</script>

<template>
  <Popover v-model:open="open">
    <PopoverTrigger
      class="bg-picker-btn"
      data-testid="bg-picker-trigger"
      :title="`外觀 — 背景:${appearance.currentOption.label}`"
      aria-label="切換背景外觀"
    >
      <span class="bg-picker-swatch" :style="{ background: appearance.currentOption.swatch }" />
      <svg
        xmlns="http://www.w3.org/2000/svg"
        width="14"
        height="14"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
        class="bg-picker-caret"
      >
        <path d="m6 9 6 6 6-6" />
      </svg>
    </PopoverTrigger>
    <PopoverContent>
      <div class="bg-picker-head">外觀 — 背景</div>
      <ul class="bg-picker-list">
        <li v-for="opt in BACKGROUNDS" :key="opt.id">
          <button
            type="button"
            class="bg-option"
            :class="{ 'bg-option--active': opt.id === appearance.current }"
            :data-testid="`bg-option-${opt.id}`"
            :aria-pressed="opt.id === appearance.current"
            @click="choose(opt.id)"
          >
            <span class="bg-option-swatch" :style="{ background: opt.swatch }" />
            <span class="bg-option-text">
              <span class="bg-option-label">{{ opt.label }}</span>
              <span class="bg-option-desc">{{ opt.description }}</span>
            </span>
            <svg
              v-if="opt.id === appearance.current"
              xmlns="http://www.w3.org/2000/svg"
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2.5"
              stroke-linecap="round"
              stroke-linejoin="round"
              class="bg-option-check"
            >
              <path d="M20 6 9 17l-5-5" />
            </svg>
          </button>
        </li>
      </ul>
    </PopoverContent>
  </Popover>
</template>

<style scoped>
.bg-picker-btn {
  display: inline-flex;
  align-items: center;
  gap: calc(var(--spacing) * 1.5);
  height: 28px;
  padding: 0 calc(var(--spacing) * 2);
  border-radius: var(--radius-sm);
  border: 1px solid var(--glass-l1-border);
  background: var(--surface-2);
  color: var(--color-text-muted);
  cursor: pointer;
  transition:
    background-color var(--duration-fast) var(--ease-glass),
    border-color var(--duration-fast) var(--ease-glass),
    color var(--duration-fast) var(--ease-glass);
}
.bg-picker-btn:hover {
  color: var(--color-text);
  background: var(--surface-3);
  border-color: var(--surface-hover-border);
}
.bg-picker-swatch {
  width: 16px;
  height: 16px;
  border-radius: 5px;
  border: 1px solid var(--glass-l1-border);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.12);
}
.bg-picker-caret {
  opacity: 0.6;
}

.bg-picker-head {
  padding: calc(var(--spacing) * 1) calc(var(--spacing) * 2) calc(var(--spacing) * 2);
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--color-text-faint);
}
.bg-picker-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin: 0;
  padding: 0;
  list-style: none;
}
.bg-option {
  display: flex;
  align-items: center;
  gap: calc(var(--spacing) * 3);
  width: 100%;
  padding: calc(var(--spacing) * 2);
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-text);
  text-align: left;
  cursor: pointer;
  transition:
    background-color var(--duration-fast) var(--ease-glass),
    border-color var(--duration-fast) var(--ease-glass);
}
.bg-option:hover {
  background: var(--surface-3);
}
.bg-option--active {
  background: var(--accent-tint);
  border-color: var(--accent-border);
}
.bg-option-swatch {
  flex: none;
  width: 40px;
  height: 28px;
  border-radius: var(--radius-xs);
  border: 1px solid var(--glass-l1-border);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.12);
}
.bg-option-text {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
}
.bg-option-label {
  font-size: 13px;
  font-weight: 600;
  line-height: 1.2;
}
.bg-option-desc {
  font-size: 11px;
  color: var(--color-text-muted);
  line-height: 1.2;
}
.bg-option-check {
  margin-left: auto;
  flex: none;
  color: var(--color-accent);
}
</style>
