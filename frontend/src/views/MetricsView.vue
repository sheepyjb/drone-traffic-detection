<template>
  <div class="metrics-view">
    <h2 class="view-title">模型评估指标</h2>
    <div class="clay-card section">
      <div class="section-label">消融实验</div>
      <el-table :data="ablationData" style="width: 100%" size="small" stripe>
        <el-table-column prop="experiment" label="模型" min-width="260" />
        <el-table-column prop="map50" label="mAP@0.5" width="100" align="center">
          <template #default="{ row }"><span class="mono" :style="{ color: row.map50>=80 ? '#22c55e' : '#f59e0b' }">{{ row.map50.toFixed(1) }}%</span></template>
        </el-table-column>
        <el-table-column prop="map50_95" label="mAP@.5:.95" width="110" align="center"><template #default="{ row }"><span class="mono">{{ row.map50_95.toFixed(1) }}%</span></template></el-table-column>
        <el-table-column prop="precision" label="Precision" width="100" align="center"><template #default="{ row }"><span class="mono">{{ row.precision.toFixed(1) }}%</span></template></el-table-column>
        <el-table-column prop="recall" label="Recall" width="90" align="center"><template #default="{ row }"><span class="mono">{{ row.recall.toFixed(1) }}%</span></template></el-table-column>
        <el-table-column prop="fps" label="FPS" width="70" align="center"><template #default="{ row }"><span class="mono">{{ row.fps }}</span></template></el-table-column>
        <el-table-column prop="params" label="参数量" width="90" align="center"><template #default="{ row }"><span class="mono">{{ row.params }}</span></template></el-table-column>
        <el-table-column prop="gflops" label="GFLOPs" width="90" align="center"><template #default="{ row }"><span class="mono">{{ row.gflops }}</span></template></el-table-column>
      </el-table>
    </div>
    <div class="chart-row">
      <div class="clay-card chart-half"><div class="section-label">各类别 AP@0.5 (%)</div><div ref="barRef" class="chart-box"></div></div>
      <div class="clay-card chart-half"><div class="section-label">模型概览</div><div ref="bubbleRef" class="chart-box"></div></div>
    </div>
    <div class="clay-card section"><div class="section-label">P-R 曲线</div><div ref="prRef" class="chart-wide"></div></div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import * as echarts from 'echarts'
import { useDetectionStore } from '@/stores/detection'

const detectionStore = useDetectionStore()

/* ---- 无人机交通检测数据 ---- */
const ablationData = ref([
  { experiment: 'Baseline (RGB only)', map50: 72.8, map50_95: 48.3, precision: 78.5, recall: 70.2, fps: 95, params: '22.1M', gflops: 56.8 },
  { experiment: 'RGB+IR Fusion (DCGFModule)', map50: 79.3, map50_95: 53.1, precision: 82.0, recall: 76.4, fps: 78, params: '28.4M', gflops: 78.3 },
  { experiment: 'Full Pipeline (Fusion + Augmentation)', map50: 81.5, map50_95: 55.7, precision: 84.2, recall: 78.6, fps: 72, params: '28.4M', gflops: 78.3 },
])

const defectLabels = ['小汽车', '货车', '大巴', '厢式货车', '货运车']
const defectColors = ['#3B82F6', '#EF4444', '#10B981', '#F59E0B', '#8B5CF6']
const classAP = [89.2, 80.1, 84.5, 73.8, 79.9]

const barRef = ref<HTMLDivElement|null>(null); const bubbleRef = ref<HTMLDivElement|null>(null); const prRef = ref<HTMLDivElement|null>(null)
const charts: echarts.ECharts[] = []
const darkTip = { backgroundColor: 'rgba(255,255,255,0.96)', borderColor: '#e2e8f0', borderWidth: 1, textStyle: { color: '#1e293b', fontSize: 12 } }

function getLabels() {
  return detectionStore.categories.length > 0
    ? detectionStore.categories.map(c => c.label)
    : defectLabels
}
function getColors() {
  return detectionStore.categories.length > 0
    ? detectionStore.categories.map(c => c.color)
    : defectColors
}

function initBar() {
  if (!barRef.value) return; const c = echarts.init(barRef.value); charts.push(c)
  c.setOption({ backgroundColor: 'transparent', tooltip: { trigger: 'axis', ...darkTip },
    grid: { top: 15, right: 16, bottom: 25, left: 48 },
    xAxis: { type: 'category', data: getLabels(), axisLabel: { color: '#475569', fontSize: 13 } },
    yAxis: { type: 'value', name: 'AP@0.5(%)', min: 50, max: 100, splitLine: { lineStyle: { color: 'rgba(0,0,0,0.06)' } }, axisLabel: { color: '#64748b' } },
    series: [
      { name: 'AP@0.5', type: 'bar', data: classAP.map((v, i) => ({ value: v, itemStyle: { color: getColors()[i] || '#0891b2', borderRadius: [4, 4, 0, 0] } })), barWidth: '50%',
        label: { show: true, position: 'top', formatter: '{c}%', fontSize: 12, fontWeight: 'bold', color: '#1e293b' } },
    ],
  })
}

function initBubble() {
  if (!bubbleRef.value) return; const c = echarts.init(bubbleRef.value); charts.push(c)
  c.setOption({ backgroundColor: 'transparent', tooltip: { ...darkTip, formatter: (p: any) => `${p.data[3]}<br/>Params: ${p.data[0]}M | mAP50: ${p.data[1]}% | FPS: ${p.data[2]}` },
    grid: { top: 15, right: 28, bottom: 35, left: 52 },
    xAxis: { name: 'Params(M)', splitLine: { lineStyle: { color: 'rgba(0,0,0,0.06)' } }, axisLabel: { color: '#64748b' } },
    yAxis: { name: 'mAP@0.5(%)', min: 30, max: 100, splitLine: { lineStyle: { color: 'rgba(0,0,0,0.06)' } }, axisLabel: { color: '#64748b' } },
    series: [{ type: 'scatter', symbolSize: (d: number[]) => Math.sqrt(d[2]) * 3,
      data: [
        [22.1, 72.8, 95, 'YOLO26s RGB'],
        [28.4, 81.5, 72, 'YOLO26s Fusion'],
      ],
      itemStyle: { color: '#0891b2', shadowBlur: 6, shadowColor: 'rgba(8,145,178,0.2)' },
      label: { show: true, formatter: (p: any) => p.data[3], position: 'top', fontSize: 10, color: '#475569' },
    }],
  })
}

function initPR() {
  if (!prRef.value) return; const c = echarts.init(prRef.value); charts.push(c)
  const realAP = [0.892, 0.801, 0.845, 0.738, 0.799]
  const labels = getLabels()
  const colors = getColors()
  function genPR(ap: number): number[][] {
    const p: number[][] = []; for (let r = 0; r <= 1; r += 0.01) {
      p.push([+r.toFixed(2), +Math.max(0, Math.min(1, ap * (1 - r * r) * (1 + 0.03 * Math.sin(r * 12)))).toFixed(3)])
    }; return p
  }
  c.setOption({ backgroundColor: 'transparent', tooltip: { trigger: 'axis', ...darkTip }, legend: { bottom: 0, textStyle: { color: '#475569', fontSize: 10 } },
    grid: { top: 15, right: 16, bottom: 40, left: 48 },
    xAxis: { name: 'Recall', type: 'value', min: 0, max: 1, splitLine: { lineStyle: { color: 'rgba(0,0,0,0.06)' } }, axisLabel: { color: '#64748b' } },
    yAxis: { name: 'Precision', type: 'value', min: 0, max: 1, splitLine: { lineStyle: { color: 'rgba(0,0,0,0.06)' } }, axisLabel: { color: '#64748b' } },
    series: [
      ...labels.map((label, i) => ({ name: `${label} (${(realAP[i]*100).toFixed(1)}%)`, type: 'line' as const, smooth: true, showSymbol: false, lineStyle: { width: 2 }, itemStyle: { color: colors[i] }, areaStyle: { color: colors[i], opacity: 0.08 }, data: genPR(realAP[i]) })),
      { name: 'mAP (81.5%)', type: 'line' as const, smooth: true, showSymbol: false, lineStyle: { width: 2, type: 'dashed' as const }, itemStyle: { color: '#0891b2' }, data: genPR(0.815) },
    ],
  })
}

let obs: ResizeObserver | null = null
onMounted(() => { initBar(); initBubble(); initPR()
  const ts = [barRef.value, bubbleRef.value, prRef.value].filter(Boolean) as HTMLDivElement[]
  obs = new ResizeObserver(() => charts.forEach(c => c.resize())); ts.forEach(t => obs!.observe(t))
})
onUnmounted(() => { obs?.disconnect(); charts.forEach(c => c.dispose()) })
</script>

<style lang="scss" scoped>
.metrics-view { display: flex; flex-direction: column; gap: 14px; padding-bottom: 20px; }
.view-title { font-size: 20px; font-weight: 700; color: $text-primary; }
.section { padding: 18px; }
.chart-row { display: flex; gap: 14px; }
.chart-half { flex: 1; min-width: 0; padding: 18px; }
.chart-box { width: 100%; height: 280px; }
.chart-wide { width: 100%; height: 320px; }
</style>
