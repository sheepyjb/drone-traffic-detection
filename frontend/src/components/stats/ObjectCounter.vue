<template>
  <div class="clay-card counter-card">
    <div class="counter-top">
      <span class="section-label">目标计数</span>
      <span class="total-badge mono">{{ detectionStore.totalObjects }}</span>
    </div>
    <div class="counter-grid">
      <div
        v-for="cat in detectionStore.categories"
        :key="cat.id"
        class="count-cell"
        :class="{ active: detectionStore.selectedCategoryId === cat.id }"
        :style="{ '--cc': cat.color }"
        @click="detectionStore.toggleCategoryFilter(cat.id)"
      >
        <div class="cb-val mono">{{ detectionStore.categoryCounts[cat.id] || 0 }}</div>
        <div class="cb-label"><span class="cb-dot" :style="{ background: cat.color }"></span>{{ cat.label }}</div>
      </div>
    </div>
    <div v-if="detectionStore.selectedCategoryId !== null" class="filter-hint" @click="detectionStore.toggleCategoryFilter(detectionStore.selectedCategoryId!)">
      过滤：{{ activeLabel }} <span class="clear-btn">× 清除</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useDetectionStore } from '@/stores/detection'
const detectionStore = useDetectionStore()

const activeLabel = computed(() => {
  const cat = detectionStore.categories.find(c => c.id === detectionStore.selectedCategoryId)
  return cat?.label || ''
})
</script>

<style lang="scss" scoped>
.counter-card { padding: 18px; }
.counter-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.total-badge {
  font-size: 14px;
  font-weight: 700;
  padding: 3px 16px;
  border-radius: $radius-sm;
  background: rgba($ind-cyan, 0.1);
  border: 1px solid rgba($ind-cyan, 0.25);
  color: $ind-cyan;
}
.counter-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.count-cell {
  background: $bg-card-alt;
  border: 1px solid $border-color;
  border-left: 3px solid var(--cc);
  border-radius: $radius-md;
  padding: 14px 10px;
  text-align: center;
  cursor: pointer;
  transition: all $transition-fast;
  &:hover { border-color: var(--cc); background: rgba(0, 0, 0, 0.02); }
  &.active {
    background: rgba(8, 145, 178, 0.06);
    border-color: var(--cc);
  }
}
.cb-val { font-size: 22px; font-weight: 700; color: $text-primary; }
.cb-label { font-size: 13px; color: $text-secondary; margin-top: 4px; display: flex; align-items: center; justify-content: center; gap: 5px; font-weight: 500; }
.cb-dot { width: 7px; height: 7px; border-radius: 50%; }
.filter-hint {
  margin-top: 10px;
  text-align: center;
  font-size: 13px;
  color: $ind-cyan;
  cursor: pointer;
  padding: 6px 0;
  border-top: 1px solid $border-color;
  font-weight: 500;
}
.clear-btn { font-weight: 700; margin-left: 4px; opacity: 0.7; &:hover { opacity: 1; } }
</style>
