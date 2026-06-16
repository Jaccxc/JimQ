<script setup lang="ts">
/**
 * 卡 #27 (P2-S1) — Research 頁(/research)佔位。
 *
 * W4 填入(模型/特徵研究 UI)。本卡僅放佔位,確保 tabbed shell 三分頁可切換。
 */
</script>

<template>
  <div class="research" data-testid="research-placeholder">
    <div class="card">
      <h1>Research</h1>
      <p>研究工作台將於 W4 填入(模型訓練/特徵分析/回測比較)。</p>
    </div>
  </div>
</template>

<style scoped>
.research { display: flex; align-items: center; justify-content: center; height: 100%; }
.card {
  text-align: center; color: #9ca3af; max-width: 420px; padding: 24px;
  border: 1px dashed #1c2230; border-radius: 10px; background: #11151d;
}
.card h1 { color: #d1d4dc; font-size: 18px; margin: 0 0 8px; }
.card p { font-size: 13px; line-height: 1.6; margin: 0; }
</style>
