<template>
  <div class="compare-view">
    <div class="view-header">
      <h2 class="view-title">模型对比</h2>
      <div class="compare-ctrl">
        <el-select v-model="leftModelId" size="small" style="width: 190px" placeholder="基线模型">
          <el-option v-for="m in models" :key="m.id" :label="m.name" :value="m.id" />
        </el-select>
        <span class="vs-badge">VS</span>
        <el-select v-model="rightModelId" size="small" style="width: 190px" placeholder="改进模型">
          <el-option v-for="m in models" :key="m.id" :label="m.name" :value="m.id" />
        </el-select>
        <button class="clay-btn primary" @click="startCompare"><el-icon><VideoPlay /></el-icon>对比</button>
      </div>
    </div>
    <div class="compare-canvas clay-card"><SplitView :left-model="leftModel?.name" :right-model="rightModel?.name" :running="comparing" /></div>
    <div class="clay-card compare-table">
      <div class="section-label">指标对比</div>
      <el-table :data="comparisonData" style="width: 100%" size="small">
        <el-table-column prop="metric" label="指标" width="140" />
        <el-table-column prop="baseline" :label="leftModel?.name || 'Baseline'" align="center" />
        <el-table-column prop="improved" :label="rightModel?.name || '改进模型'" align="center">
          <template #default="{ row }"><span :class="{ better: row.improved_better }">{{ row.improved }}</span></template>
        </el-table-column>
        <el-table-column prop="diff" label="变化" align="center">
          <template #default="{ row }"><span class="mono" :style="{ color: row.diff_positive ? '#22c55e' : '#ef4444' }">{{ row.diff }}</span></template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { VideoPlay } from '@element-plus/icons-vue'
import SplitView from '@/components/compare/SplitView.vue'
import { useAppStore } from '@/stores/app'
const appStore = useAppStore()
const models = computed(() => appStore.availableModels)
const leftModelId = ref('yolo26s-rgb')
const rightModelId = ref('yolo26s-fusion')
const comparing = ref(false)
const leftModel = computed(() => models.value.find(m => m.id === leftModelId.value))
const rightModel = computed(() => models.value.find(m => m.id === rightModelId.value))
const comparisonData = computed(() => {
  const l = leftModel.value, r = rightModel.value; if (!l || !r) return []
  return [
    { metric: 'mAP@0.5', baseline: `${l.map50}%`, improved: `${r.map50}%`, diff: `+${(r.map50-l.map50).toFixed(1)}%`, improved_better: r.map50>l.map50, diff_positive: r.map50>l.map50 },
    { metric: 'FPS', baseline: l.fps, improved: r.fps, diff: r.fps>l.fps ? `+${r.fps-l.fps}` : `${r.fps-l.fps}`, improved_better: r.fps>l.fps, diff_positive: r.fps>l.fps },
    { metric: '参数量', baseline: l.params, improved: r.params, diff: '-', improved_better: false, diff_positive: true },
    { metric: 'GFLOPs', baseline: l.gflops, improved: r.gflops, diff: `+${(r.gflops-l.gflops).toFixed(1)}`, improved_better: r.gflops<l.gflops, diff_positive: r.gflops<l.gflops },
  ]
})
function startCompare() { comparing.value = true }
</script>

<style lang="scss" scoped>
.compare-view { height: 100%; display: flex; flex-direction: column; gap: 14px; }
.view-header { display: flex; justify-content: space-between; align-items: center; }
.view-title { font-size: 20px; font-weight: 700; color: $text-primary; }
.compare-ctrl { display: flex; align-items: center; gap: 12px; }
.vs-badge { font-size: 13px; font-weight: 700; font-family: $font-mono; padding: 5px 14px; background: rgba($ind-amber, 0.1); color: $ind-amber; border: 1px solid rgba($ind-amber, 0.25); border-radius: $radius-sm; }
.compare-canvas { flex: 1; min-height: 250px; padding: 0; overflow: hidden; }
.compare-table { padding: 18px; .better { color: $ind-green; font-weight: 700; } }
</style>
