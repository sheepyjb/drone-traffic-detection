<template>
  <div class="clay-card pr-card">
    <div class="section-label">P-R 曲线</div>
    <div ref="chartRef" class="chart-area"></div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import * as echarts from 'echarts'
import { useDetectionStore } from '@/stores/detection'

const detectionStore = useDetectionStore()
const chartRef = ref<HTMLDivElement | null>(null)
let chart: echarts.ECharts | null = null

function genPR(maxP: number): number[][] {
  const pts: number[][] = []
  for (let r = 0; r <= 1.0; r += 0.02) { pts.push([+r.toFixed(2), +Math.min(maxP * Math.exp(-1.5 * r) * (1 + 0.1 * Math.sin(r * 10)), 1).toFixed(3)]) }
  return pts
}

let obs: ResizeObserver | null = null
onMounted(() => {
  if (!chartRef.value) return
  chart = echarts.init(chartRef.value)
  chart.setOption({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis', backgroundColor: 'rgba(255,255,255,0.9)', borderColor: '#e0d4f0', textStyle: { color: '#4a3a6b', fontSize: 11 } },
    legend: { bottom: 0, textStyle: { fontSize: 10, color: '#7b6a9e' } },
    grid: { top: 10, right: 16, bottom: 36, left: 42 },
    xAxis: { name: 'Recall', type: 'value', min: 0, max: 1, splitLine: { lineStyle: { color: 'rgba(196,161,255,0.12)' } } },
    yAxis: { name: 'Prec.', type: 'value', min: 0, max: 1, splitLine: { lineStyle: { color: 'rgba(196,161,255,0.12)' } } },
    series: detectionStore.categories.map((c: { label: string; color: string }, i: number) => ({ name: c.label, type: 'line' as const, smooth: true, showSymbol: false, lineStyle: { width: 2.5 }, itemStyle: { color: c.color }, areaStyle: { color: c.color, opacity: 0.06 }, data: genPR(0.95 - i * 0.06) })),
  })
  obs = new ResizeObserver(() => chart?.resize()); obs.observe(chartRef.value)
})
onUnmounted(() => { obs?.disconnect(); chart?.dispose() })
</script>

<style lang="scss" scoped>
.pr-card { padding: 14px; }
.chart-area { width: 100%; height: 210px; }
</style>
