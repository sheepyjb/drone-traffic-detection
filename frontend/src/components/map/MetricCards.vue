<template>
  <div class="metric-cards">
    <div class="metric-card">
      <div class="metric-value">{{ detectionStore.totalObjects }}</div>
      <div class="metric-label">当前目标</div>
    </div>
    <div class="metric-card accent">
      <div class="metric-value">{{ flowCountStore.totalVehicleCount }}</div>
      <div class="metric-label">累计车辆</div>
    </div>
    <div class="metric-card" :class="congestionClass">
      <div class="metric-value congestion-text">{{ flowCountStore.congestionLevel }}</div>
      <div class="metric-label">拥堵状态</div>
    </div>
    <div class="metric-card">
      <div class="metric-value">{{ flowCountStore.stoppedCount }}</div>
      <div class="metric-label">静止车辆</div>
    </div>

    <!-- 方向统计 -->
    <div class="metric-card">
      <div class="metric-value">{{ flowCountStore.directionSummary.north }}</div>
      <div class="metric-label">北向</div>
    </div>
    <div class="metric-card">
      <div class="metric-value">{{ flowCountStore.directionSummary.south }}</div>
      <div class="metric-label">南向</div>
    </div>
    <div class="metric-card">
      <div class="metric-value">{{ flowCountStore.directionSummary.west }}</div>
      <div class="metric-label">西向</div>
    </div>
    <div class="metric-card">
      <div class="metric-value">{{ flowCountStore.directionSummary.east }}</div>
      <div class="metric-label">东向</div>
    </div>

    <!-- 交通指标 -->
    <div class="metric-card wide">
      <div class="metric-value">{{ flowCountStore.maxQueueLength }}</div>
      <div class="metric-label">排队长度 (m)</div>
    </div>
    <div class="metric-card wide los-card" :style="{ '--los-color': flowCountStore.serviceLevelColor }">
      <div class="metric-value los-value">{{ flowCountStore.serviceLevelGrade }}</div>
      <div class="metric-label">服务水平</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useDetectionStore } from '@/stores/detection'
import { useFlowCountStore } from '@/stores/flowCount'

const detectionStore = useDetectionStore()
const flowCountStore = useFlowCountStore()

const congestionClass = computed(() => {
  const level = flowCountStore.congestionLevel
  if (level === '严重拥堵') return 'danger'
  if (level === '拥堵') return 'warning'
  if (level === '缓行') return 'caution'
  return 'ok'
})
</script>

<style lang="scss" scoped>
.metric-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 6px;
  padding: 12px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
}

.metric-card {
  text-align: center;
  padding: 8px 4px;
  background: rgba(0, 0, 0, 0.02);
  border-radius: 8px;
  border: 1px solid rgba(0, 0, 0, 0.04);

  &.wide { grid-column: span 2; }
  &.accent {
    background: rgba(8, 145, 178, 0.06);
    border-color: rgba(8, 145, 178, 0.15);
    .metric-value { color: #0891b2; }
  }
  &.ok { background: rgba(34,197,94,0.06); .congestion-text { color: #22c55e; } }
  &.caution { background: rgba(245,158,11,0.06); .congestion-text { color: #f59e0b; } }
  &.warning { background: rgba(239,68,68,0.06); .congestion-text { color: #ef4444; } }
  &.danger { background: rgba(220,38,38,0.08); .congestion-text { color: #dc2626; } }
}

.metric-value {
  font-size: 18px;
  font-weight: 800;
  color: #1e293b;
  font-variant-numeric: tabular-nums;
  font-family: 'JetBrains Mono', monospace;
  line-height: 1.2;
}

.metric-label {
  font-size: 10px;
  color: #94a3b8;
  font-weight: 500;
  margin-top: 2px;
}

.los-card {
  background: color-mix(in srgb, var(--los-color) 8%, transparent);
  border-color: color-mix(in srgb, var(--los-color) 20%, transparent);
}

.los-value {
  color: var(--los-color) !important;
  font-size: 22px;
}
</style>
