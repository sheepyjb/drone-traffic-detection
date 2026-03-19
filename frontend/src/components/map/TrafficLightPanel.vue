<template>
  <div class="panel-section" v-if="mapStore.trafficLightState">
    <div class="section-title">
      <el-icon><Sunrise /></el-icon>
      信号灯配时
    </div>

    <!-- 信号灯动画 -->
    <div class="light-display">
      <div class="light-group">
        <div class="light-label">南北</div>
        <div class="light-bulb" :class="nsPhaseClass">
          <span class="light-text">{{ nsPhaseText }}</span>
        </div>
      </div>
      <div class="countdown">
        <span class="countdown-num">{{ mapStore.trafficLightState.greenRemaining }}</span>
        <span class="countdown-unit">秒</span>
      </div>
      <div class="light-group">
        <div class="light-label">东西</div>
        <div class="light-bulb" :class="ewPhaseClass">
          <span class="light-text">{{ ewPhaseText }}</span>
        </div>
      </div>
    </div>

    <!-- 方向车流 -->
    <div class="direction-grid">
      <div v-for="d in mapStore.trafficLightState.directions" :key="d.name" class="direction-item">
        <span class="dir-label">{{ d.label }}</span>
        <span class="dir-count">{{ d.vehicleCount }}辆</span>
        <span class="dir-green">{{ d.greenSeconds }}s</span>
      </div>
    </div>

    <!-- Webster 参数面板 -->
    <div v-if="websterParams" class="webster-panel">
      <div class="webster-title">Webster 优化参数</div>
      <div class="webster-grid">
        <div class="webster-item">
          <span class="w-label">最优周期</span>
          <span class="w-value">{{ websterParams.optimalCycle }}s</span>
        </div>
        <div class="webster-item">
          <span class="w-label">总损失时间</span>
          <span class="w-value">{{ websterParams.totalLossTime }}s</span>
        </div>
        <div class="webster-item">
          <span class="w-label">饱和流量</span>
          <span class="w-value">{{ websterParams.saturationFlow }}</span>
        </div>
        <div class="webster-item">
          <span class="w-label">总流量比 Y</span>
          <span class="w-value">{{ websterParams.sumFlowRatio.toFixed(3) }}</span>
        </div>
      </div>
      <!-- 各相位流量比 -->
      <div class="phase-ratios">
        <div v-for="p in websterParams.phaseFlowRatios" :key="p.name" class="phase-row">
          <span class="phase-name">{{ p.name }}</span>
          <div class="phase-bar-wrap">
            <div class="phase-bar" :style="{ width: `${Math.min(p.flowRatio / 0.5 * 100, 100)}%` }"></div>
          </div>
          <span class="phase-ratio">y={{ p.flowRatio.toFixed(3) }}</span>
          <span class="phase-green">{{ p.greenTime }}s</span>
        </div>
      </div>
      <!-- 延误减少 -->
      <div v-if="websterParams.estimatedDelayReduction > 0" class="delay-reduction">
        优化后预计减少延误 <strong>{{ websterParams.estimatedDelayReduction }}%</strong>
      </div>
    </div>

    <!-- 配时报告 -->
    <el-collapse>
      <el-collapse-item title="配时策略报告" name="report">
        <pre class="report-text">{{ mapStore.trafficLightState.report }}</pre>
      </el-collapse-item>
    </el-collapse>
  </div>

  <div class="panel-section panel-empty" v-else>
    <div class="section-title">
      <el-icon><Sunrise /></el-icon>
      信号灯配时
    </div>
    <p class="empty-hint">点击"配时分析"生成信号灯策略</p>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Sunrise } from '@element-plus/icons-vue'
import { useMapStore } from '@/stores/map'

const mapStore = useMapStore()

const nsPhaseClass = computed(() => {
  const phase = mapStore.trafficLightState?.currentPhase
  return phase === 'NS' ? 'green' : 'red'
})

const ewPhaseClass = computed(() => {
  const phase = mapStore.trafficLightState?.currentPhase
  return phase === 'EW' ? 'green' : 'red'
})

const nsPhaseText = computed(() => nsPhaseClass.value === 'green' ? '行' : '停')
const ewPhaseText = computed(() => ewPhaseClass.value === 'green' ? '行' : '停')

const websterParams = computed(() => mapStore.trafficLightState?.websterParams)
</script>

<style lang="scss" scoped>
.light-display {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 20px;
  padding: 12px 0;
}

.light-group {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
}

.light-label {
  font-size: 12px;
  color: $text-muted;
  font-weight: 600;
}

.light-bulb {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.5s ease;
  border: 3px solid rgba(0, 0, 0, 0.1);

  &.green {
    background: #22c55e;
    box-shadow: 0 0 16px rgba(34, 197, 94, 0.6);
  }
  &.red {
    background: #ef4444;
    box-shadow: 0 0 16px rgba(239, 68, 68, 0.6);
  }
}

.light-text {
  color: #fff;
  font-size: 14px;
  font-weight: 700;
}

.countdown {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.countdown-num {
  font-size: 28px;
  font-weight: 800;
  color: $text-primary;
  font-variant-numeric: tabular-nums;
}

.countdown-unit {
  font-size: 11px;
  color: $text-muted;
}

.direction-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 6px;
  margin-top: 10px;
}

.direction-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 6px 4px;
  background: rgba(0, 0, 0, 0.03);
  border-radius: 6px;
}

.dir-label {
  font-size: 12px;
  font-weight: 600;
  color: $text-secondary;
}
.dir-count {
  font-size: 13px;
  font-weight: 700;
  color: $text-primary;
}
.dir-green {
  font-size: 11px;
  color: #22c55e;
  font-weight: 500;
}

// Webster 参数面板
.webster-panel {
  margin-top: 12px;
  padding: 10px;
  background: rgba(59, 130, 246, 0.04);
  border: 1px solid rgba(59, 130, 246, 0.1);
  border-radius: 8px;
}

.webster-title {
  font-size: 12px;
  font-weight: 700;
  color: #3b82f6;
  margin-bottom: 8px;
}

.webster-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
}

.webster-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 3px 0;
}

.w-label {
  font-size: 11px;
  color: #64748b;
}

.w-value {
  font-size: 12px;
  font-weight: 700;
  color: #1e293b;
  font-family: 'JetBrains Mono', monospace;
}

.phase-ratios {
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.phase-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.phase-name {
  font-size: 11px;
  color: #64748b;
  width: 28px;
  flex-shrink: 0;
}

.phase-bar-wrap {
  flex: 1;
  height: 6px;
  background: rgba(0, 0, 0, 0.06);
  border-radius: 3px;
  overflow: hidden;
}

.phase-bar {
  height: 100%;
  background: #3b82f6;
  border-radius: 3px;
  transition: width 0.3s ease;
}

.phase-ratio {
  font-size: 10px;
  color: #94a3b8;
  font-family: 'JetBrains Mono', monospace;
  width: 56px;
  text-align: right;
}

.phase-green {
  font-size: 11px;
  color: #22c55e;
  font-weight: 600;
  width: 28px;
  text-align: right;
}

.delay-reduction {
  margin-top: 8px;
  padding: 6px 8px;
  background: rgba(34, 197, 94, 0.08);
  border-radius: 6px;
  font-size: 12px;
  color: #16a34a;
  text-align: center;

  strong {
    font-size: 14px;
    font-weight: 800;
  }
}

.report-text {
  font-size: 12px;
  line-height: 1.6;
  color: $text-secondary;
  white-space: pre-wrap;
  word-break: break-all;
  margin: 0;
}

.empty-hint {
  font-size: 13px;
  color: $text-muted;
  text-align: center;
  padding: 8px 0;
}

.panel-section {
  padding: 16px;
  border-bottom: 1px solid $border-color;
}
</style>
