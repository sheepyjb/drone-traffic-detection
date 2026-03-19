<template>
  <div class="chart-section">
    <div class="section-header">
      <span class="section-icon">&#xe616;</span>
      断面流量
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
  const lines = flowCountStore.virtualLines
  const xData = lines.map(l => l.name)
  const positiveData = lines.map(l => flowCountStore.lineCounts[l.id]?.positive || 0)
  const negativeData = lines.map(l => flowCountStore.lineCounts[l.id]?.negative || 0)

  return {
    tooltip: { trigger: 'axis', textStyle: { fontSize: 11 } },
    legend: {
      data: ['正向(下/右穿)', '反向(上/左穿)'],
      top: 0, right: 0,
      textStyle: { fontSize: 10, color: '#64748b' },
      itemWidth: 12, itemHeight: 8,
    },
    grid: { left: 36, right: 8, top: 28, bottom: 20 },
    xAxis: {
      type: 'category',
      data: xData,
      axisLabel: { fontSize: 10, color: '#64748b' },
      axisLine: { lineStyle: { color: '#e2e8f0' } },
    },
    yAxis: {
      type: 'value',
      minInterval: 1,
      axisLabel: { fontSize: 10, color: '#94a3b8' },
      splitLine: { lineStyle: { color: '#f1f5f9' } },
    },
    series: [
      {
        name: '正向(下/右穿)',
        type: 'bar',
        data: positiveData,
        itemStyle: { color: '#3B82F6', borderRadius: [3, 3, 0, 0] },
        barWidth: '30%',
      },
      {
        name: '反向(上/左穿)',
        type: 'bar',
        data: negativeData,
        itemStyle: { color: '#EF4444', borderRadius: [3, 3, 0, 0] },
        barWidth: '30%',
      },
    ],
  }
}

// 节流：最多 500ms 更新一次 ECharts
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

watch(
  () => flowCountStore.totalCrossed,
  () => throttledUpdate(),
)

onUnmounted(() => {
  if (updateTimer) clearTimeout(updateTimer)
  obs?.disconnect()
  chart?.dispose()
})
</script>

<style lang="scss" scoped>
.chart-section {
  padding: 12px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
}
.section-header {
  font-size: 12px;
  font-weight: 700;
  color: #1e293b;
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  gap: 4px;
}
.chart-box {
  width: 100%;
  height: 160px;
}
</style>
