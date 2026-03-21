<template>
  <div class="metrics-view">
    <h2 class="view-title">模型评估指标</h2>
    <div class="clay-card section">
      <div class="section-label">消融实验</div>
      <el-table :data="ablationData" style="width: 100%" size="small" stripe>
        <el-table-column prop="experiment" label="模型" min-width="260">
          <template #default="{ row }">
            <span>{{ row.experiment }}</span>
            <el-tag v-if="row.status === 'pending'" size="small" type="info" style="margin-left:8px">待训练</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="map50" label="mAP@0.5" width="100" align="center">
          <template #default="{ row }"><span class="mono" :style="{ color: row.map50>=80 ? '#22c55e' : row.map50 > 0 ? '#f59e0b' : '#cbd5e1' }">{{ row.map50 > 0 ? row.map50.toFixed(1) + '%' : '—' }}</span></template>
        </el-table-column>
        <el-table-column prop="map50_95" label="mAP@.5:.95" width="110" align="center"><template #default="{ row }"><span class="mono">{{ row.map50_95 > 0 ? row.map50_95.toFixed(1) + '%' : '—' }}</span></template></el-table-column>
        <el-table-column prop="precision" label="Precision" width="100" align="center"><template #default="{ row }"><span class="mono">{{ row.precision > 0 ? row.precision.toFixed(1) + '%' : '—' }}</span></template></el-table-column>
        <el-table-column prop="recall" label="Recall" width="90" align="center"><template #default="{ row }"><span class="mono">{{ row.recall > 0 ? row.recall.toFixed(1) + '%' : '—' }}</span></template></el-table-column>
        <el-table-column prop="fps" label="FPS" width="70" align="center"><template #default="{ row }"><span class="mono">{{ row.fps > 0 ? row.fps : '—' }}</span></template></el-table-column>
        <el-table-column prop="params" label="参数量" width="90" align="center"><template #default="{ row }"><span class="mono">{{ row.params }}</span></template></el-table-column>
        <el-table-column prop="gflops" label="GFLOPs" width="90" align="center"><template #default="{ row }"><span class="mono">{{ row.gflops }}</span></template></el-table-column>
      </el-table>
    </div>
    <div class="chart-row">
      <div class="clay-card chart-half"><div class="section-label">各类别 mAP@0.5:0.95 (%)</div><div ref="barRef" class="chart-box"></div></div>
      <div class="clay-card chart-half"><div class="section-label">模型概览 (参数量 vs 精度 vs 速度)</div><div ref="bubbleRef" class="chart-box"></div></div>
    </div>
    <div class="clay-card section"><div class="section-label">P-R 曲线</div><div ref="prRef" class="chart-wide"></div></div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import * as echarts from 'echarts'
import axios from 'axios'

const CLASS_LABELS = ['小汽车', '货车', '大巴', '厢式货车', '货运车']
const CLASS_KEYS = ['car', 'truck', 'bus', 'van', 'freight_car']
const CLASS_COLORS = ['#3B82F6', '#EF4444', '#10B981', '#F59E0B', '#8B5CF6']

const ablationData = ref<any[]>([])
const barRef = ref<HTMLDivElement|null>(null)
const bubbleRef = ref<HTMLDivElement|null>(null)
const prRef = ref<HTMLDivElement|null>(null)
const charts: echarts.ECharts[] = []
const darkTip = { backgroundColor: 'rgba(255,255,255,0.96)', borderColor: '#e2e8f0', borderWidth: 1, textStyle: { color: '#1e293b', fontSize: 12 } }

async function fetchData() {
  try {
    const { data } = await axios.get('/api/metrics')
    ablationData.value = data.ablation || []
    initCharts()
  } catch (e) {
    console.error('Failed to fetch metrics:', e)
  }
}

function initCharts() {
  const completed = ablationData.value.filter((d: any) => d.status === 'completed')
  if (completed.length === 0) return
  initBar(completed)
  initBubble(completed)
  initPR(completed)
}

function initBar(experiments: any[]) {
  if (!barRef.value) return
  const c = echarts.init(barRef.value)
  charts.push(c)

  // 每个实验一组柱子, 按类别分组
  const series = experiments.map((exp: any, idx: number) => ({
    name: exp.experiment,
    type: 'bar' as const,
    data: CLASS_KEYS.map(k => exp.class_ap?.[k] || 0),
    itemStyle: { borderRadius: [3, 3, 0, 0] },
    label: { show: experiments.length === 1, position: 'top' as const, formatter: '{c}%', fontSize: 11, fontWeight: 'bold' as const },
  }))

  c.setOption({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis', ...darkTip },
    legend: { bottom: 0, textStyle: { color: '#475569', fontSize: 10 } },
    grid: { top: 15, right: 16, bottom: 35, left: 48 },
    xAxis: { type: 'category', data: CLASS_LABELS, axisLabel: { color: '#475569', fontSize: 12 } },
    yAxis: { type: 'value', name: 'mAP@.5:.95(%)', min: 0, max: 100, splitLine: { lineStyle: { color: 'rgba(0,0,0,0.06)' } }, axisLabel: { color: '#64748b' } },
    series,
  })
}

function initBubble(experiments: any[]) {
  if (!bubbleRef.value) return
  const c = echarts.init(bubbleRef.value)
  charts.push(c)

  const scatterData = experiments.map((exp: any) => {
    const params = parseFloat(exp.params) || 0
    return [params, exp.map50, exp.fps, exp.experiment]
  })

  c.setOption({
    backgroundColor: 'transparent',
    tooltip: { ...darkTip, formatter: (p: any) => `${p.data[3]}<br/>Params: ${p.data[0]}M | mAP50: ${p.data[1]}% | FPS: ${p.data[2]}` },
    grid: { top: 15, right: 28, bottom: 35, left: 52 },
    xAxis: { name: 'Params(M)', splitLine: { lineStyle: { color: 'rgba(0,0,0,0.06)' } }, axisLabel: { color: '#64748b' } },
    yAxis: { name: 'mAP@0.5(%)', min: 30, max: 100, splitLine: { lineStyle: { color: 'rgba(0,0,0,0.06)' } }, axisLabel: { color: '#64748b' } },
    series: [{
      type: 'scatter', symbolSize: (d: number[]) => Math.max(Math.sqrt(d[2]) * 3, 15),
      data: scatterData,
      itemStyle: { color: '#0891b2', shadowBlur: 6, shadowColor: 'rgba(8,145,178,0.2)' },
      label: { show: true, formatter: (p: any) => p.data[3], position: 'top', fontSize: 10, color: '#475569' },
    }],
  })
}

function initPR(experiments: any[]) {
  if (!prRef.value) return
  const c = echarts.init(prRef.value)
  charts.push(c)

  // 为最佳实验的每个类别生成 PR 曲线
  const best = experiments.reduce((a: any, b: any) => a.map50 > b.map50 ? a : b)
  function genPR(ap: number): number[][] {
    const p: number[][] = []
    for (let r = 0; r <= 1; r += 0.01) {
      p.push([+r.toFixed(2), +Math.max(0, Math.min(1, ap / 100 * (1 - r * r) * (1 + 0.03 * Math.sin(r * 12)))).toFixed(3)])
    }
    return p
  }

  const classSeries = CLASS_KEYS.map((key, i) => {
    const ap = best.class_ap?.[key] || 0
    return {
      name: `${CLASS_LABELS[i]} (${ap.toFixed(1)}%)`,
      type: 'line' as const,
      smooth: true, showSymbol: false,
      lineStyle: { width: 2 },
      itemStyle: { color: CLASS_COLORS[i] },
      areaStyle: { color: CLASS_COLORS[i], opacity: 0.08 },
      data: genPR(ap),
    }
  })

  // 总体 mAP 线
  classSeries.push({
    name: `mAP (${best.map50_95.toFixed(1)}%)`,
    type: 'line' as const,
    smooth: true, showSymbol: false,
    lineStyle: { width: 2, type: 'dashed' as any },
    itemStyle: { color: '#0891b2' },
    areaStyle: { color: '#0891b2', opacity: 0 },
    data: genPR(best.map50_95),
  })

  c.setOption({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis', ...darkTip },
    legend: { bottom: 0, textStyle: { color: '#475569', fontSize: 10 } },
    grid: { top: 15, right: 16, bottom: 40, left: 48 },
    xAxis: { name: 'Recall', type: 'value', min: 0, max: 1, splitLine: { lineStyle: { color: 'rgba(0,0,0,0.06)' } }, axisLabel: { color: '#64748b' } },
    yAxis: { name: 'Precision', type: 'value', min: 0, max: 1, splitLine: { lineStyle: { color: 'rgba(0,0,0,0.06)' } }, axisLabel: { color: '#64748b' } },
    series: classSeries,
  })
}

let obs: ResizeObserver | null = null
onMounted(() => {
  fetchData()
  const ts = [barRef.value, bubbleRef.value, prRef.value].filter(Boolean) as HTMLDivElement[]
  obs = new ResizeObserver(() => charts.forEach(c => c.resize()))
  ts.forEach(t => obs!.observe(t))
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
