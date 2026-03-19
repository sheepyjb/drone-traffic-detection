<template>
  <div class="chart-section">
    <div class="section-header">车型构成</div>
    <div ref="pieRef" class="chart-box"></div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted } from 'vue'
import * as echarts from 'echarts'
import { useDetectionStore } from '@/stores/detection'

const detectionStore = useDetectionStore()
const pieRef = ref<HTMLElement>()
let chart: echarts.ECharts | null = null

const CLASS_COLORS: Record<number, string> = {
  0: '#3B82F6', 1: '#EF4444', 2: '#10B981', 3: '#F59E0B', 4: '#8B5CF6',
}
const CLASS_LABELS: Record<number, string> = {
  0: '小汽车', 1: '货车', 2: '大巴', 3: '厢式货车', 4: '货运车',
}

function getOption(): echarts.EChartsOption {
  const counts = detectionStore.categoryCounts
  const data = Object.entries(counts)
    .filter(([, v]) => v > 0)
    .map(([k, v]) => ({
      name: CLASS_LABELS[Number(k)] || `类别${k}`,
      value: v,
      itemStyle: { color: CLASS_COLORS[Number(k)] || '#94a3b8' },
    }))

  if (data.length === 0) {
    data.push({ name: '暂无数据', value: 0, itemStyle: { color: '#e2e8f0' } })
  }

  return {
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)', textStyle: { fontSize: 11 } },
    legend: {
      orient: 'vertical',
      right: 4, top: 'center',
      textStyle: { fontSize: 10, color: '#64748b' },
      itemWidth: 10, itemHeight: 10,
    },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      center: ['35%', '50%'],
      avoidLabelOverlap: false,
      label: {
        show: true,
        position: 'inside',
        fontSize: 10,
        fontWeight: 600,
        color: '#fff',
        formatter: (p: any) => p.value > 0 ? `${p.value}` : '',
      },
      data,
      emphasis: {
        itemStyle: { shadowBlur: 8, shadowColor: 'rgba(0,0,0,0.15)' },
      },
    }],
  }
}

// 节流：最多 500ms 更新一次 ECharts（避免每帧重绘）
let updateTimer: ReturnType<typeof setTimeout> | null = null
function throttledUpdate() {
  if (updateTimer) return
  updateTimer = setTimeout(() => {
    updateTimer = null
    chart?.setOption(getOption(), { notMerge: true })
  }, 500)
}

let obs: ResizeObserver | null = null
onMounted(() => {
  if (pieRef.value) {
    chart = echarts.init(pieRef.value)
    chart.setOption(getOption())
    obs = new ResizeObserver(() => chart?.resize())
    obs.observe(pieRef.value)
  }
})

watch(() => detectionStore.totalObjects, () => throttledUpdate())
onUnmounted(() => { if (updateTimer) clearTimeout(updateTimer); obs?.disconnect(); chart?.dispose() })
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
}
.chart-box {
  width: 100%;
  height: 150px;
}
</style>
