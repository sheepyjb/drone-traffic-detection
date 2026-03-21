<template>
  <div class="chart-section">
    <div class="section-header">
      {{ flowCountStore.linesEnabled ? '断面流量' : '方向车流量' }}
    </div>
    <div ref="barRef" class="chart-box"></div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted } from 'vue'
import * as echarts from 'echarts'
import { useFlowCountStore } from '@/stores/flowCount'

const flowCountStore = useFlowCountStore()
const barRef = ref<HTMLElement>()
let chart: echarts.ECharts | null = null

function getOption(): echarts.EChartsOption {
  if (flowCountStore.linesEnabled) {
    // 虚拟线模式: 按线统计
    const lines = flowCountStore.virtualLines
    return {
      tooltip: { trigger: 'axis', textStyle: { fontSize: 11 } },
      legend: { data: ['正向', '反向'], top: 0, right: 0, textStyle: { fontSize: 10, color: '#64748b' }, itemWidth: 12, itemHeight: 8 },
      grid: { left: 36, right: 8, top: 28, bottom: 20 },
      xAxis: { type: 'category', data: lines.map(l => l.name), axisLabel: { fontSize: 10, color: '#64748b' } },
      yAxis: { type: 'value', minInterval: 1, axisLabel: { fontSize: 10, color: '#94a3b8' }, splitLine: { lineStyle: { color: '#f1f5f9' } } },
      series: [
        { name: '正向', type: 'bar', data: lines.map(l => flowCountStore.lineCounts[l.id]?.positive || 0), itemStyle: { color: '#3B82F6', borderRadius: [3, 3, 0, 0] }, barWidth: '30%' },
        { name: '反向', type: 'bar', data: lines.map(l => flowCountStore.lineCounts[l.id]?.negative || 0), itemStyle: { color: '#EF4444', borderRadius: [3, 3, 0, 0] }, barWidth: '30%' },
      ],
    }
  }

  // 自动模式: 按方向统计
  const dirs = flowCountStore.directionSummary
  const colors = ['#3B82F6', '#EF4444', '#F59E0B', '#10B981']
  return {
    tooltip: { trigger: 'axis', textStyle: { fontSize: 11 } },
    grid: { left: 36, right: 8, top: 12, bottom: 20 },
    xAxis: { type: 'category', data: ['北向', '南向', '西向', '东向'], axisLabel: { fontSize: 10, color: '#64748b' } },
    yAxis: { type: 'value', minInterval: 1, axisLabel: { fontSize: 10, color: '#94a3b8' }, splitLine: { lineStyle: { color: '#f1f5f9' } } },
    series: [{
      type: 'bar', barWidth: '45%',
      data: [
        { value: dirs.north, itemStyle: { color: colors[0], borderRadius: [3, 3, 0, 0] } },
        { value: dirs.south, itemStyle: { color: colors[1], borderRadius: [3, 3, 0, 0] } },
        { value: dirs.west, itemStyle: { color: colors[2], borderRadius: [3, 3, 0, 0] } },
        { value: dirs.east, itemStyle: { color: colors[3], borderRadius: [3, 3, 0, 0] } },
      ],
    }],
  }
}

let updateTimer: ReturnType<typeof setTimeout> | null = null
function throttledUpdate() {
  if (updateTimer) return
  updateTimer = setTimeout(() => {
    updateTimer = null
    if (chart) chart.setOption(getOption(), { notMerge: true })
  }, 500)
}

let obs: ResizeObserver | null = null
onMounted(() => {
  if (barRef.value) {
    chart = echarts.init(barRef.value)
    chart.setOption(getOption())
    obs = new ResizeObserver(() => chart?.resize())
    obs.observe(barRef.value)
  }
})

watch(() => [flowCountStore.totalVehicleCount, flowCountStore.totalCrossed, flowCountStore.linesEnabled], () => throttledUpdate())

onUnmounted(() => {
  if (updateTimer) clearTimeout(updateTimer)
  obs?.disconnect(); chart?.dispose()
})
</script>

<style lang="scss" scoped>
.chart-section { padding: 12px; border-bottom: 1px solid rgba(0, 0, 0, 0.06); }
.section-header { font-size: 12px; font-weight: 700; color: #1e293b; margin-bottom: 8px; }
.chart-box { width: 100%; height: 160px; }
</style>
