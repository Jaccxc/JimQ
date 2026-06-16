<script setup lang="ts">
/**
 * Backtest 回放控制列(受控 UI;不自管回放狀態)。
 *
 * props 驅動顯示(playing / currentIndex / total / speed),互動 emit 事件交由
 * 父層的回放引擎(useReplayPlayer)處理:▶/⏸、速度滑桿(1~50 根/秒)、進度條
 * (scrub 可拖)、↺ 重播、⏭ 跳到結尾(顯示完整)。
 *
 * 玻璃樣式沿用 theme.css token(L2 玻璃條);data-testid 齊全供測試。
 */
const props = defineProps<{
  playing: boolean
  /** 0-based 當前 index。 */
  currentIndex: number
  /** bar 總數。 */
  total: number
  /** 播放速度(根/秒)。 */
  speed: number
}>()

const emit = defineEmits<{
  play: []
  pause: []
  'set-speed': [value: number]
  scrub: [index: number]
  replay: []
  'to-end': []
}>()

function onPlayPause() {
  if (props.total === 0) return
  if (props.playing) emit('pause')
  else emit('play')
}

function onSpeed(e: Event) {
  emit('set-speed', Number((e.target as HTMLInputElement).value))
}

function onScrub(e: Event) {
  emit('scrub', Number((e.target as HTMLInputElement).value))
}
</script>

<template>
  <div class="replay-controls" data-testid="replay-controls">
    <button
      class="ctrl-btn play"
      data-testid="replay-playpause"
      :disabled="total === 0"
      :title="playing ? '暫停' : '播放'"
      @click="onPlayPause"
    >
      <span v-if="playing">⏸</span>
      <span v-else>▶</span>
    </button>

    <button
      class="ctrl-btn"
      data-testid="replay-restart"
      :disabled="total === 0"
      title="重播"
      @click="emit('replay')"
    >
      ↺
    </button>

    <button
      class="ctrl-btn"
      data-testid="replay-to-end"
      :disabled="total === 0"
      title="跳到結尾(顯示完整)"
      @click="emit('to-end')"
    >
      ⏭
    </button>

    <!-- 進度條:可拖 scrub 到任意位置。 -->
    <input
      class="progress"
      type="range"
      data-testid="replay-progress"
      min="0"
      :max="Math.max(0, total - 1)"
      :value="currentIndex"
      :disabled="total === 0"
      @input="onScrub"
    />
    <span class="position" data-testid="replay-position">
      {{ total === 0 ? 0 : currentIndex + 1 }} / {{ total }}
    </span>

    <!-- 速度滑桿 1~50 根/秒。 -->
    <div class="speed-group">
      <input
        class="speed"
        type="range"
        data-testid="replay-speed"
        min="1"
        max="50"
        step="1"
        :value="speed"
        @input="onSpeed"
      />
      <span class="speed-label" data-testid="replay-speed-label">{{ speed }} 根/秒</span>
    </div>
  </div>
</template>

<style scoped>
/* 玻璃化控制條(L2)。token 來自 styles/theme.css。 */
.replay-controls {
  display: flex;
  align-items: center;
  gap: calc(var(--spacing) * 2);
  padding: calc(var(--spacing) * 1.5) calc(var(--spacing) * 2);
  background: var(--glass-l2-bg);
  border: 1px solid var(--glass-l1-border);
  border-radius: var(--radius-sm);
  box-shadow: var(--glass-l1-highlight);
  backdrop-filter: blur(var(--glass-l2-blur)) saturate(var(--glass-l1-saturate));
  -webkit-backdrop-filter: blur(var(--glass-l2-blur)) saturate(var(--glass-l1-saturate));
}
@supports not (backdrop-filter: blur(1px)) {
  .replay-controls { background: var(--glass-fallback-bg); }
}
.ctrl-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 30px;
  height: 30px;
  padding: 0 calc(var(--spacing) * 1.5);
  font-size: 13px;
  line-height: 1;
  color: var(--color-text);
  background: var(--surface-1);
  border: 1px solid var(--glass-l1-border);
  border-radius: var(--radius-xs);
  cursor: pointer;
  transition: background var(--duration-fast) var(--ease-glass),
    border-color var(--duration-fast) var(--ease-glass);
}
.ctrl-btn:hover:not(:disabled) {
  background: var(--accent-tint);
  border-color: var(--accent-border);
}
.ctrl-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.ctrl-btn.play {
  color: #a78bfa;
}
.progress {
  flex: 1;
  min-width: 120px;
  accent-color: #a78bfa;
  cursor: pointer;
}
.position {
  font-size: 12px;
  font-variant-numeric: tabular-nums;
  color: var(--color-text-muted);
  white-space: nowrap;
  min-width: 72px;
  text-align: right;
}
.speed-group {
  display: flex;
  align-items: center;
  gap: calc(var(--spacing) * 1);
}
.speed {
  width: 96px;
  accent-color: #a78bfa;
  cursor: pointer;
}
.speed-label {
  font-size: 12px;
  font-variant-numeric: tabular-nums;
  color: var(--color-text-muted);
  white-space: nowrap;
  min-width: 56px;
}
</style>
