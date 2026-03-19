<template>
  <div class="clay-card perf-card">
    <div class="section-label">性能指标</div>
    <div class="perf-grid">
      <div v-for="item in perfItems" :key="item.label" class="perf-cell">
        <div class="pv mono" :style="{ color: item.color }">{{ item.value }}</div>
        <div class="pl">{{ item.label }}</div>
        <div class="pb-track"><div class="pb-fill" :style="{ width: item.pct + '%', background: item.color }"></div></div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useDetectionStore } from '@/stores/detection'
const detectionStore = useDetectionStore()
const perfItems = computed(() => [
  { label: 'FPS', value: detectionStore.fps.toFixed(1), color: detectionStore.fps >= 25 ? '#22c55e' : detectionStore.fps >= 15 ? '#f59e0b' : '#ef4444', pct: Math.min(100, (detectionStore.fps / 30) * 100) },
  { label: '延迟(ms)', value: detectionStore.latency.toFixed(1), color: detectionStore.latency <= 15 ? '#22c55e' : '#f59e0b', pct: Math.min(100, (detectionStore.latency / 50) * 100) },
  { label: '目标数', value: String(detectionStore.totalObjects), color: '#06b6d4', pct: Math.min(100, (detectionStore.totalObjects / 20) * 100) },
  { label: '帧号', value: String(detectionStore.frameId), color: '#3b82f6', pct: 0 },
])
</script>

<style lang="scss" scoped>
.perf-card { padding: 18px; }
.perf-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.perf-cell {
  text-align: center;
  padding: 14px 8px;
  background: $bg-card-alt;
  border: 1px solid $border-color;
  border-radius: $radius-md;
}
.pv { font-size: 24px; font-weight: 700; }
.pl { font-size: 13px; color: $text-muted; margin-top: 3px; font-weight: 500; }
.pb-track { height: 4px; background: rgba(0, 0, 0, 0.06); border-radius: 2px; margin-top: 8px; overflow: hidden; }
.pb-fill { height: 100%; border-radius: 2px; transition: width 0.2s ease-out; }
</style>
