<template>
  <div class="command-center">
    <!-- ===== 中央航拍态势图（全屏底层） ===== -->
    <div class="map-layer">
      <AerialView ref="aerialRef" />
    </div>

    <!-- ===== 左侧：AR 视频流悬浮窗 ===== -->
    <VideoStreamPanel />

    <!-- ===== 右侧：数据看板 ===== -->
    <div class="dashboard-panel" :class="{ collapsed: dashCollapsed }">
      <div class="dash-toggle" @click="dashCollapsed = !dashCollapsed">
        {{ dashCollapsed ? '&#9664;' : '&#9654;' }}
      </div>
      <div v-show="!dashCollapsed" class="dash-content">
        <el-scrollbar>
          <!-- 指标卡 -->
          <MetricCards />

          <!-- 断面流量柱状图 -->
          <FlowBarChart />

          <!-- 车型构成环形图 -->
          <VehiclePieChart />

          <!-- 信号灯配时 -->
          <TrafficLightPanel />

          <!-- 转向分析 -->
          <TurnPieChart />

          <!-- 事件预警 -->
          <EventAlertPanel />

          <!-- 无人机参数 (折叠) -->
          <div class="param-section">
            <el-collapse>
              <el-collapse-item title="无人机参数" name="drone">
                <div class="param-grid">
                  <div class="param-item">
                    <label>纬度</label>
                    <el-input-number v-model="mapStore.droneParams.lat" :step="0.0001" :precision="4" size="small" controls-position="right" />
                  </div>
                  <div class="param-item">
                    <label>经度</label>
                    <el-input-number v-model="mapStore.droneParams.lng" :step="0.0001" :precision="4" size="small" controls-position="right" />
                  </div>
                  <div class="param-item">
                    <label>高度 (m)</label>
                    <el-input-number v-model="mapStore.droneParams.altitude" :min="10" :max="500" :step="10" size="small" controls-position="right" />
                  </div>
                  <div class="param-item">
                    <label>俯仰角</label>
                    <el-input-number v-model="mapStore.droneParams.pitch" :min="-90" :max="0" :step="5" size="small" controls-position="right" />
                  </div>
                  <div class="param-item">
                    <label>水平FOV</label>
                    <el-input-number v-model="mapStore.droneParams.hFov" :min="30" :max="120" :step="2" size="small" controls-position="right" />
                  </div>
                  <div class="param-item">
                    <label>垂直FOV</label>
                    <el-input-number v-model="mapStore.droneParams.vFov" :min="20" :max="90" :step="2" size="small" controls-position="right" />
                  </div>
                </div>
              </el-collapse-item>
            </el-collapse>
          </div>

          <!-- 操作按钮 -->
          <div class="action-section">
            <el-button type="success" size="small" @click="analyzeTraffic" :loading="analyzing">
              配时分析
            </el-button>
            <el-button type="warning" size="small" @click="exportReport">
              导出报告
            </el-button>
          </div>
        </el-scrollbar>
      </div>
    </div>

    <!-- ===== 底部状态栏 ===== -->
    <div class="status-bar">
      <div class="status-item">
        <span class="status-dot" :class="detectionStore.isDetecting ? 'active' : ''"></span>
        {{ detectionStore.isDetecting ? '检测中' : '待机' }}
      </div>
      <div class="status-item">
        YOLO26 | DroneVehicle | 5-Class
      </div>
      <div class="status-item" v-if="detectionStore.fps > 0">
        {{ detectionStore.fps.toFixed(1) }} FPS | {{ detectionStore.latency }}ms
      </div>
      <div class="status-item ml-auto">
        {{ mapStore.droneParams.lat.toFixed(4) }}, {{ mapStore.droneParams.lng.toFixed(4) }} | {{ mapStore.droneParams.altitude }}m
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { ElNotification } from 'element-plus'
import { useMapStore } from '@/stores/map'
import { useDetectionStore } from '@/stores/detection'
import { useFlowCountStore } from '@/stores/flowCount'
import AerialView from '@/components/map/AerialView.vue'
import VideoStreamPanel from '@/components/map/VideoStreamPanel.vue'
import MetricCards from '@/components/map/MetricCards.vue'
import FlowBarChart from '@/components/map/FlowBarChart.vue'
import VehiclePieChart from '@/components/map/VehiclePieChart.vue'
import TrafficLightPanel from '@/components/map/TrafficLightPanel.vue'
import TurnPieChart from '@/components/map/TurnPieChart.vue'
import EventAlertPanel from '@/components/map/EventAlertPanel.vue'


const mapStore = useMapStore()
const detectionStore = useDetectionStore()
const flowCountStore = useFlowCountStore()
const aerialRef = ref()
const analyzing = ref(false)
const dashCollapsed = ref(false)

async function analyzeTraffic() {
  if (mapStore.mappedVehicles.length === 0) {
    ElNotification({ title: '提示', message: '暂无检测数据，请先运行检测', type: 'warning', duration: 3000 })
    return
  }
  analyzing.value = true
  try {
    await mapStore.analyzeTraffic()
    ElNotification({ title: '配时分析完成', message: '信号灯策略已生成', type: 'success', duration: 2000 })
  } finally {
    analyzing.value = false
  }
}

function exportReport() {
  const fc = flowCountStore
  const s = mapStore.trafficLightState
  const p = mapStore.droneParams

  let text = '=== 无人机智慧交通检测报告 ===\n\n'
  text += `生成时间: ${new Date().toLocaleString()}\n`
  text += `模型: YOLO26 | 数据集: DroneVehicle\n\n`
  text += `--- 无人机参数 ---\n`
  text += `位置: (${p.lat}, ${p.lng}) | 高度: ${p.altitude}m\n`
  text += `FOV: ${p.hFov}° x ${p.vFov}°\n\n`
  text += `--- 虚拟线圈流量统计 ---\n`
  text += `累计过线车辆: ${fc.totalCrossed}\n`
  text += `北侧: ${fc.directionSummary.north} | 南侧: ${fc.directionSummary.south} | 西侧: ${fc.directionSummary.west} | 东侧: ${fc.directionSummary.east}\n`
  text += `车型分布:\n`
  const labels: Record<number, string> = { 0: '小汽车', 1: '货车', 2: '大巴', 3: '厢式货车', 4: '货运车' }
  for (const [k, v] of Object.entries(fc.classCounts)) {
    if (v > 0) text += `  ${labels[Number(k)] || k}: ${v}\n`
  }
  text += '\n'

  // 拥堵指标
  text += `--- 交通拥堵评价 ---\n`
  text += `最大排队长度: ${fc.maxQueueLength}m\n`
  text += `平均延误: ${fc.avgDelay}s\n`
  text += `平均占有率: ${fc.avgOccupancy}%\n`
  text += `服务水平: ${fc.serviceLevelGrade}\n\n`

  // 转向分析
  if (fc.turns.length > 0) {
    text += `--- 转向分析 ---\n`
    text += `总转向记录: ${fc.turns.length}\n`
    const ts = fc.turnSummary
    for (const dir of ['south', 'north', 'west', 'east'] as const) {
      const dirLabel: Record<string, string> = { south: '南进', north: '北进', west: '西进', east: '东进' }
      const s = ts[dir]
      const total = s.straight + s.left + s.right + s.uturn
      if (total > 0) {
        text += `  ${dirLabel[dir]}: 直行${s.straight} 左转${s.left} 右转${s.right} 掉头${s.uturn}\n`
      }
    }
    text += '\n'
  }

  // 事件预警
  if (fc.trafficEvents.length > 0) {
    text += `--- 事件预警记录 ---\n`
    for (const evt of fc.trafficEvents.slice(0, 20)) {
      text += `  [${new Date(evt.timestamp).toLocaleTimeString()}] ${evt.message}\n`
    }
    text += '\n'
  }

  if (s) {
    text += `--- 配时策略 ---\n${s.report}\n\n`
  }

  const blob = new Blob([text], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `traffic_report_${Date.now()}.txt`
  a.click()
  URL.revokeObjectURL(url)
}
</script>

<style lang="scss" scoped>
.command-center {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
}

// ===== 地图底层 =====
.map-layer {
  position: absolute;
  inset: 0;
  z-index: 1;
}

// ===== 右侧看板 =====
.dashboard-panel {
  position: absolute;
  top: 0;
  right: 0;
  bottom: 32px;
  width: 320px;
  background: rgba(255, 255, 255, 0.97);
  border-left: 1px solid rgba(0, 0, 0, 0.08);
  z-index: 100;
  display: flex;
  transition: width 0.3s ease;

  &.collapsed {
    width: 0;
    .dash-content { display: none; }
  }
}

.dash-toggle {
  position: absolute;
  left: -24px;
  top: 50%;
  transform: translateY(-50%);
  width: 24px;
  height: 48px;
  background: rgba(255, 255, 255, 0.95);
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-right: none;
  border-radius: 6px 0 0 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  font-size: 10px;
  color: #94a3b8;
  z-index: 101;

  &:hover { color: #0891b2; background: #fff; }
}

.dash-content {
  flex: 1;
  overflow: hidden;
}

// ===== 参数/操作 =====
.param-section {
  padding: 4px 12px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
}

.param-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.param-item {
  display: flex;
  flex-direction: column;
  gap: 3px;

  label {
    font-size: 10px;
    color: #94a3b8;
    font-weight: 500;
  }

  .el-input-number { width: 100%; }
}

.action-section {
  padding: 12px;
  display: flex;
  gap: 8px;
}

// ===== 底部状态栏 =====
.status-bar {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 32px;
  background: rgba(255, 255, 255, 0.95);
  border-top: 1px solid rgba(0, 0, 0, 0.06);
  z-index: 200;
  display: flex;
  align-items: center;
  padding: 0 16px;
  gap: 16px;
  font-size: 11px;
  color: #64748b;
  font-family: 'JetBrains Mono', monospace;
}

.status-item {
  display: flex;
  align-items: center;
  gap: 4px;

  &.ml-auto { margin-left: auto; }
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #94a3b8;

  &.active {
    background: #22c55e;
    box-shadow: 0 0 4px rgba(34, 197, 94, 0.6);
    animation: blink 1.5s infinite;
  }
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
</style>
