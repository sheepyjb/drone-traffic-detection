<template>
  <div class="chart-section">
    <div class="section-header">转向分析</div>
    <div v-if="hasTurnData" ref="chartRef" class="chart-box"></div>
    <div v-else class="empty-hint">暂无转向数据（需穿越两条以上检测线）</div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import * as echarts from 'echarts'
import { useFlowCountStore } from '@/stores/flowCount'

const flowCountStore = useFlowCountStore()
const chartRef = ref<HTMLElement>()
let chart: echarts.ECharts | null = null

const DIR_LABELS: Record<string, string> = {
  north: '北进', south: '南进', east: '东进', west: '西进',
}

const TURN_COLORS: Record<string, string> = {
  straight: '#3B82F6',
  left: '#F59E0B',
  right: '#10B981',
  uturn: '#EF4444',
  unknown: '#94A3B8',
}

const hasTurnData = computed(() => flowCountStore.turns.length > 0)

function getOption(): echarts.EChartsOption {
  const summary = flowCountStore.turnSummary
  const labels = flowCountStore.TURN_LABELS
  const dirs = ['south', 'north', 'west', 'east'] as const
  const turnTypes = ['straight', 'left', 'right', 'uturn'] as const

  // 堆叠柱状图：每个方向一组，每种转向一层
  const categories = dirs.map(d => DIR_LABELS[d])
  const series = turnTypes.map(tt => ({
    name: labels[tt],
    type: 'bar' as const,
    stack: 'turn',
    barWidth: 24,
    itemStyle: { color: TURN_COLORS[tt], borderRadius: tt === 'uturn' ? [3, 3, 0, 0] : 0 },
    data: dirs.map(d => summary[d]?.[tt] || 0),
  }))

  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      textStyle: { fontSize: 12 },
    },
    legend: {
      top: 0,
      left: 'center',
      itemWidth: 10,
      itemHeight: 10,
      itemGap: 12,
      textStyle: { fontSize: 10, color: '#64748b' },
    },
    grid: { left: 36, right: 12, top: 32, bottom: 24 },
    xAxis: {
      type: 'category',
      data: categories,
      axisLabel: { fontSize: 10, color: '#64748b' },
      axisLine: { show: false },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value',
      axisLabel: { fontSize: 10, color: '#94a3b8' },
      splitLine: { lineStyle: { color: 'rgba(0,0,0,0.04)' } },
    },
    series,
  }
}

let updateTimer: ReturnType<typeof setTimeout> | null = null
function throttledUpdateChart() {
  if (updateTimer) return
  updateTimer = setTimeout(() => {
    updateTimer = null
    if (chart && hasTurnData.value) chart.setOption(getOption())
  }, 500)
}

function initChart() {
  if (!chartRef.value) return
  chart = echarts.init(chartRef.value)
  if (hasTurnData.value) chart.setOption(getOption())
}

watch(() => flowCountStore.turns.length, throttledUpdateChart)
watch(hasTurnData, (v) => {
  if (v) {
    setTimeout(initChart, 50)
  }
})

let obs: ResizeObserver | null = null
onMounted(() => {
  if (hasTurnData.value) initChart()
  obs = new ResizeObserver(() => chart?.resize())
  if (chartRef.value) obs.observe(chartRef.value)
})
onUnmounted(() => {
  if (updateTimer) clearTimeout(updateTimer)
  chart?.dispose()
  obs?.disconnect()
})
</script>

<style lang="scss" scoped>
.chart-section {
  padding: 12px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
}

.section-header {
  font-size: 13px;
  font-weight: 700;
  color: #1e293b;
  margin-bottom: 8px;
}

.chart-box {
  width: 100%;
  height: 200px;
}

.empty-hint {
  font-size: 12px;
  color: #94a3b8;
  text-align: center;
  padding: 16px 0;
}
</style>
