<template>
  <div class="clay-split">
    <div class="split-half left">
      <div class="half-bar"><span class="badge-base">Baseline</span><span class="half-model">{{ leftModel || '-' }}</span></div>
      <div class="half-canvas"><canvas ref="leftCanvasRef"></canvas><div class="half-empty" v-if="!running">STANDBY</div></div>
      <div class="half-stat mono"><span>FPS: {{ leftFps.toFixed(1) }}</span><span>目标: {{ leftCount }}</span></div>
    </div>
    <div class="split-mid"><span class="vs-pill">VS</span></div>
    <div class="split-half right">
      <div class="half-bar"><span class="badge-imp">改进版</span><span class="half-model">{{ rightModel || '-' }}</span></div>
      <div class="half-canvas"><canvas ref="rightCanvasRef"></canvas><div class="half-empty" v-if="!running">STANDBY</div></div>
      <div class="half-stat mono"><span>FPS: {{ rightFps.toFixed(1) }}</span><span>目标: {{ rightCount }}</span></div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
defineProps<{ leftModel?: string; rightModel?: string; running?: boolean }>()
const leftCanvasRef = ref<HTMLCanvasElement | null>(null)
const rightCanvasRef = ref<HTMLCanvasElement | null>(null)
const leftFps = ref(0); const rightFps = ref(0)
const leftCount = ref(0); const rightCount = ref(0)
</script>

<style lang="scss" scoped>
.clay-split { display: flex; height: 100%; gap: 0; }
.split-half { flex: 1; display: flex; flex-direction: column; }
.split-mid { width: 40px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.vs-pill {
  font-size: 12px; font-weight: 800; padding: 6px 10px;
  background: $clay-orange; color: white;
  border-radius: $radius-pill;
  box-shadow: $shadow-clay-pressed, $clay-inset;
}
.half-bar {
  display: flex; align-items: center; gap: 8px; padding: 8px 14px;
  background: rgba(255, 255, 255, 0.4); border-bottom: 1px solid $border-light;
}
.badge-base { font-size: 11px; font-weight: 700; padding: 2px 10px; border-radius: $radius-pill; background: rgba(255, 123, 123, 0.15); color: $clay-red; }
.badge-imp { font-size: 11px; font-weight: 700; padding: 2px 10px; border-radius: $radius-pill; background: rgba(110, 207, 142, 0.15); color: #4a9e65; }
.half-model { font-size: 12px; color: $text-muted; }
.half-canvas { flex: 1; position: relative; background: #e2daf0; canvas { width: 100%; height: 100%; display: block; } }
.half-empty { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; color: $text-muted; font-size: 13px; font-weight: 700; letter-spacing: 2px; }
.half-stat { display: flex; gap: 16px; padding: 6px 14px; background: rgba(255, 255, 255, 0.4); border-top: 1px solid $border-light; font-size: 11px; color: $text-muted; }
</style>
