<template>
  <div class="clay-card pie-card">
    <div class="section-label">目标分布</div>
    <div ref="chartRef" class="chart-area"></div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted } from 'vue'
import * as echarts from 'echarts'
import { useDetectionStore } from '@/stores/detection'

const detectionStore = useDetectionStore()
const chartRef = ref<HTMLDivElement | null>(null)
let chart: echarts.ECharts | null = null

function updateChart() {
  if (!chart) return
  const data = detectionStore.categories.map(c => ({
    name: c.label, value: detectionStore.categoryCounts[c.id] || 0,
    itemStyle: { color: c.color, borderColor: '#ffffff', borderWidth: 2 },
  })).filter(d => d.value > 0)
  chart.setOption({
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)', backgroundColor: 'rgba(255,255,255,0.96)', borderColor: '#e2e8f0', textStyle: { color: '#1e293b' } },
    series: [{ type: 'pie', radius: ['38%', '68%'], center: ['50%', '55%'], data: data.length ? data : [{ name: '暂无', value: 1, itemStyle: { color: '#e2e8f0' } }],
      label: { color: '#475569', fontSize: 12, fontFamily: 'Inter', fontWeight: 500 }, emphasis: { itemStyle: { shadowBlur: 8, shadowColor: 'rgba(8,145,178,0.2)' } },
    }],
  })
}

watch(() => detectionStore.categoryCounts, updateChart, { deep: true })
let obs: ResizeObserver | null = null
onMounted(() => {
  if (chartRef.value) { chart = echarts.init(chartRef.value); chart.setOption({ backgroundColor: 'transparent' }); updateChart()
    obs = new ResizeObserver(() => chart?.resize()); obs.observe(chartRef.value) }
})
onUnmounted(() => { obs?.disconnect(); chart?.dispose() })
</script>

<style lang="scss" scoped>
.pie-card { padding: 18px; }
.chart-area { width: 100%; height: 210px; }
</style>
