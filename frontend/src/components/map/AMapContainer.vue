<template>
  <div ref="mapContainer" id="amap-container" class="amap-container"></div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted, type PropType } from 'vue'
import { useAMap } from '@/composables/useAMap'
import type { GpsPoint } from '@/types'

const props = defineProps({
  dronePosition: { type: Array as PropType<number[]>, default: () => [120.1, 30.271] },
  fovPolygon: { type: Array as PropType<GpsPoint[]>, default: () => [] },
  trajectory: { type: Array as PropType<GpsPoint[]>, default: () => [] },
  vehicleDensity: { type: Number, default: 0 },
})

const mapContainer = ref<HTMLElement>()
const { map, AMap, ready, initMap } = useAMap('amap-container')

let droneMarker: any = null
let fovOverlay: any = null
let trajectoryLine: any = null
let densityCircle: any = null

onMounted(async () => {
  await initMap(props.dronePosition as [number, number], 16)
  drawDroneMarker()
  drawFovPolygon()
  drawTrajectory()
  drawDensityCircle()
})

// ===== 无人机图标 =====
function getDroneIcon() {
  return `<div style="
    display:flex;flex-direction:column;align-items:center;
    filter: drop-shadow(0 2px 8px rgba(8, 145, 178, 0.5));
  ">
    <svg width="36" height="36" viewBox="0 0 24 24" fill="none">
      <path d="M12 2L8 6H4V10L2 12L4 14V18H8L12 22L16 18H20V14L22 12L20 10V6H16L12 2Z"
        fill="#0891b2" stroke="#fff" stroke-width="1.5"/>
      <circle cx="12" cy="12" r="3" fill="#fff"/>
    </svg>
    <div style="
      margin-top:2px;font-size:9px;color:#fff;
      background:rgba(8,145,178,0.85);padding:1px 6px;
      border-radius:3px;font-weight:600;white-space:nowrap;
    ">UAV-01</div>
  </div>`
}

function drawDroneMarker() {
  if (!map.value || !AMap.value) return
  const _AMap = AMap.value
  droneMarker = new _AMap.Marker({
    position: new _AMap.LngLat(props.dronePosition[0], props.dronePosition[1]),
    content: getDroneIcon(),
    offset: new _AMap.Pixel(-18, -18),
    zIndex: 300,
  })
  droneMarker.setMap(map.value)
}

// ===== FOV 覆盖区域 =====
function drawFovPolygon() {
  if (!map.value || !AMap.value || props.fovPolygon.length < 3) return
  const _AMap = AMap.value
  const path = props.fovPolygon.map(p => new _AMap.LngLat(p.lng, p.lat))
  fovOverlay = new _AMap.Polygon({
    path,
    fillColor: '#0891b2',
    fillOpacity: 0.08,
    strokeColor: '#0891b2',
    strokeWeight: 2,
    strokeOpacity: 0.5,
    strokeStyle: 'dashed',
  })
  fovOverlay.setMap(map.value)
}

// ===== 巡航轨迹 =====
function drawTrajectory() {
  if (!map.value || !AMap.value || props.trajectory.length < 2) return
  const _AMap = AMap.value
  const path = props.trajectory.map(p => new _AMap.LngLat(p.lng, p.lat))
  trajectoryLine = new _AMap.Polyline({
    path,
    strokeColor: '#0891b2',
    strokeWeight: 3,
    strokeOpacity: 0.6,
    strokeStyle: 'dashed',
    showDir: true,
  })
  trajectoryLine.setMap(map.value)
}

// ===== 密度热力圈 =====
function drawDensityCircle() {
  if (!map.value || !AMap.value) return
  const _AMap = AMap.value
  const density = props.vehicleDensity
  const color = density >= 20 ? '#ef4444' : density >= 10 ? '#f59e0b' : '#22c55e'

  densityCircle = new _AMap.Circle({
    center: new _AMap.LngLat(props.dronePosition[0], props.dronePosition[1]),
    radius: 80,
    fillColor: color,
    fillOpacity: density > 0 ? 0.15 : 0,
    strokeColor: color,
    strokeWeight: density > 0 ? 1.5 : 0,
    strokeOpacity: 0.4,
  })
  densityCircle.setMap(map.value)
}

// 响应参数变化
watch(() => props.dronePosition, (pos) => {
  if (droneMarker && AMap.value) {
    droneMarker.setPosition(new AMap.value.LngLat(pos[0], pos[1]))
  }
  if (densityCircle && AMap.value) {
    densityCircle.setCenter(new AMap.value.LngLat(pos[0], pos[1]))
  }
}, { deep: true })

watch(() => props.fovPolygon, () => {
  if (fovOverlay) { fovOverlay.setMap(null); fovOverlay = null }
  drawFovPolygon()
}, { deep: true })

watch(() => props.vehicleDensity, (density) => {
  if (!densityCircle) return
  const color = density >= 20 ? '#ef4444' : density >= 10 ? '#f59e0b' : '#22c55e'
  densityCircle.setOptions({
    fillColor: color,
    fillOpacity: density > 0 ? 0.15 : 0,
    strokeColor: color,
    strokeWeight: density > 0 ? 1.5 : 0,
  })
})

onUnmounted(() => {
  if (droneMarker) droneMarker.setMap(null)
  if (fovOverlay) fovOverlay.setMap(null)
  if (trajectoryLine) trajectoryLine.setMap(null)
  if (densityCircle) densityCircle.setMap(null)
})

defineExpose({ map, ready })
</script>

<style scoped>
.amap-container {
  width: 100%;
  height: 100%;
  min-height: 400px;
}
</style>
