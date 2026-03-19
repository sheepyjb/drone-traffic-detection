<template>
  <div class="metric-cards">
    <div class="metric-card">
      <div class="metric-value">{{ detectionStore.totalObjects }}</div>
      <div class="metric-label">当前检测</div>
    </div>
    <div class="metric-card accent">
      <div class="metric-value">{{ flowCountStore.totalCrossed }}</div>
      <div class="metric-label">累计过线</div>
    </div>
    <div class="metric-card">
      <div class="metric-value">{{ flowCountStore.directionSummary.north }}</div>
      <div class="metric-label">北侧</div>
    </div>
    <div class="metric-card">
      <div class="metric-value">{{ flowCountStore.directionSummary.south }}</div>
      <div class="metric-label">南侧</div>
    </div>
    <div class="metric-card">
      <div class="metric-value">{{ flowCountStore.directionSummary.west }}</div>
      <div class="metric-label">西侧</div>
    </div>
    <div class="metric-card">
      <div class="metric-value">{{ flowCountStore.directionSummary.east }}</div>
      <div class="metric-label">东侧</div>
    </div>

    <!-- 专业交通指标 -->
    <div class="metric-card wide">
      <div class="metric-value">{{ flowCountStore.maxQueueLength }}</div>
      <div class="metric-label">最大排队 (m)</div>
    </div>
    <div class="metric-card wide">
      <div class="metric-value">{{ flowCountStore.avgDelay }}</div>
      <div class="metric-label">平均延误 (s)</div>
    </div>
    <div class="metric-card wide">
      <div class="metric-value">{{ flowCountStore.avgOccupancy }}%</div>
      <div class="metric-label">平均占有率</div>
    </div>
    <div class="metric-card wide los-card" :style="{ '--los-color': flowCountStore.serviceLevelColor }">
      <div class="metric-value los-value">{{ flowCountStore.serviceLevelGrade }}</div>
      <div class="metric-label">服务水平 (LOS)</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useDetectionStore } from '@/stores/detection'
import { useFlowCountStore } from '@/stores/flowCount'

const detectionStore = useDetectionStore()
const flowCountStore = useFlowCountStore()
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

  &.wide {
    grid-column: span 2;
  }

  &.accent {
    background: rgba(8, 145, 178, 0.06);
    border-color: rgba(8, 145, 178, 0.15);
    .metric-value { color: #0891b2; }
  }
}

.metric-value {
  font-size: 20px;
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
  font-size: 24px;
}
</style>
