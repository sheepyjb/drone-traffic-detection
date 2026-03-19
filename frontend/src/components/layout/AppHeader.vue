<template>
  <header class="ind-header">
    <div class="header-left">
      <div class="logo-block">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="3"/>
          <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/>
        </svg>
      </div>
      <div class="system-title">
        <span class="title-main">无人机交通检测</span>
        <span class="title-sub">DRONE TRAFFIC DETECTION</span>
      </div>
    </div>
    <div class="header-center">
      <ModelSelector />
    </div>
    <div class="header-right">
      <div class="conn-indicator" :class="{ online: appStore.wsConnected }">
        <span class="conn-dot"></span>
        {{ appStore.wsConnected ? 'ONLINE' : 'OFFLINE' }}
      </div>
    </div>
  </header>
</template>

<script setup lang="ts">
import { useAppStore } from '@/stores/app'
import ModelSelector from '@/components/controls/ModelSelector.vue'

const appStore = useAppStore()
</script>

<style lang="scss" scoped>
.ind-header {
  height: $header-height;
  background: $bg-secondary;
  border-bottom: 1px solid $border-color;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  flex-shrink: 0;
  position: relative;
  z-index: 10;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.05);
}
.header-left { display: flex; align-items: center; gap: 14px; }
.logo-block {
  width: 40px; height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba($ind-cyan, 0.1);
  color: $ind-cyan;
  border: 1px solid rgba($ind-cyan, 0.25);
  border-radius: $radius-md;
}
.system-title { display: flex; flex-direction: column; line-height: 1.3; }
.title-main { font-size: 17px; font-weight: 700; color: $text-primary; }
.title-sub { font-size: 10px; color: $text-muted; letter-spacing: 1.5px; font-weight: 600; }
.header-center { display: flex; align-items: center; }
.header-right { display: flex; align-items: center; gap: 14px; }
.conn-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  font-family: $font-mono;
  letter-spacing: 0.5px;
  padding: 5px 14px;
  border-radius: $radius-sm;
  background: rgba($ind-red, 0.08);
  border: 1px solid rgba($ind-red, 0.25);
  color: $ind-red;
  .conn-dot { width: 7px; height: 7px; border-radius: 50%; background: $ind-red; }
  &.online {
    background: rgba($ind-green, 0.08);
    border-color: rgba($ind-green, 0.25);
    color: $ind-green;
    .conn-dot { background: $ind-green; }
  }
}
</style>
