<template>
  <aside class="ind-sidebar" :class="{ collapsed: appStore.sidebarCollapsed }">
    <nav class="sidebar-nav">
      <router-link
        v-for="item in navItems"
        :key="item.path"
        :to="item.path"
        class="nav-item"
        :class="{ active: currentRoute === item.path }"
      >
        <div class="nav-icon" :style="{ '--accent': item.color }">
          <el-icon :size="16"><component :is="item.icon" /></el-icon>
        </div>
        <span v-if="!appStore.sidebarCollapsed" class="nav-text">{{ item.label }}</span>
      </router-link>
    </nav>
    <div class="sidebar-footer">
      <button class="toggle-btn" @click="appStore.toggleSidebar()">
        <el-icon :size="14">
          <DArrowLeft v-if="!appStore.sidebarCollapsed" />
          <DArrowRight v-else />
        </el-icon>
      </button>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useAppStore } from '@/stores/app'
import { Aim, CopyDocument, DataAnalysis, DArrowLeft, DArrowRight, Location } from '@element-plus/icons-vue'

const route = useRoute()
const appStore = useAppStore()
const currentRoute = computed(() => route.path)

const navItems = [
  { path: '/', label: '实时检测', icon: Aim, color: '#06b6d4' },
  { path: '/compare', label: '模型对比', icon: CopyDocument, color: '#3b82f6' },
  { path: '/metrics', label: '评估指标', icon: DataAnalysis, color: '#22c55e' },
  { path: '/map', label: '地图监控', icon: Location, color: '#f59e0b' },
]
</script>

<style lang="scss" scoped>
.ind-sidebar {
  width: $sidebar-width;
  background: $bg-secondary;
  border-right: 1px solid $border-color;
  display: flex;
  flex-direction: column;
  transition: width $transition-smooth;
  flex-shrink: 0;
  position: relative;
  z-index: 5;
  &.collapsed { width: $sidebar-collapsed-width; .nav-text { display: none; } }
}
.sidebar-nav {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 16px 10px;
  gap: 6px;
}
.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  border-radius: $radius-md;
  text-decoration: none;
  color: $text-secondary;
  font-weight: 600;
  font-size: 14px;
  transition: all $transition-fast;
  border: 1px solid transparent;

  &:hover {
    background: rgba(0, 0, 0, 0.04);
    color: $text-primary;
  }
  &.active {
    background: rgba(8, 145, 178, 0.08);
    border-color: rgba(8, 145, 178, 0.2);
    color: $ind-cyan;
  }
}
.nav-icon {
  width: 34px; height: 34px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: $radius-sm;
  color: var(--accent, $ind-cyan);
  background: rgba(0, 0, 0, 0.04);
  border: 1px solid rgba(0, 0, 0, 0.06);
  flex-shrink: 0;
}
.nav-text { white-space: nowrap; }
.sidebar-footer { padding: 10px; border-top: 1px solid $border-color; }
.toggle-btn {
  width: 100%;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  border: 1px solid transparent;
  background: transparent;
  color: $text-muted;
  border-radius: $radius-sm;
  transition: all $transition-fast;
  &:hover { background: rgba(0, 0, 0, 0.04); color: $text-primary; border-color: $border-color; }
}
</style>
