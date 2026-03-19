<template>
  <div class="clay-controls">
    <button class="ctrl-btn" @click="$emit('toggle-play')">
      <el-icon :size="14"><VideoPlay v-if="!playing" /><VideoPause v-else /></el-icon>
    </button>
    <button class="ctrl-btn" @click="$emit('stop')">
      <el-icon :size="14"><CloseBold /></el-icon>
    </button>
    <div class="ctrl-slider"><el-slider :model-value="progress" :show-tooltip="false" :step="0.1" size="small" @change="(val: number) => $emit('seek', val)" /></div>
    <span class="ctrl-time mono">{{ formatTime(currentTime) }} / {{ formatTime(duration) }}</span>
  </div>
</template>

<script setup lang="ts">
import { VideoPlay, VideoPause, CloseBold } from '@element-plus/icons-vue'

defineProps<{
  progress: number
  currentTime: number
  duration: number
  playing: boolean
}>()

defineEmits<{
  stop: []
  'toggle-play': []
  seek: [val: number]
}>()

function formatTime(sec: number): string {
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}
</script>

<style lang="scss" scoped>
.clay-controls {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 16px;
  background: $bg-card;
  border: 1px solid $border-color;
  border-radius: $radius-lg;
  box-shadow: $shadow-panel;
}
.ctrl-btn {
  width: 36px; height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: $bg-card-alt;
  border: 1px solid $border-color;
  border-radius: $radius-md;
  color: $text-secondary;
  cursor: pointer;
  transition: all $transition-fast;
  &:hover { transform: scale(1.08); color: $ind-cyan; border-color: $ind-cyan; }
  &:active { transform: scale(0.95); }
}
.ctrl-slider { flex: 1; }
.ctrl-time { font-size: 13px; color: $text-secondary; font-weight: 500; }
</style>
