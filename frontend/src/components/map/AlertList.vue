<template>
  <div class="panel-section">
    <div class="section-title">
      <el-icon><Warning /></el-icon>
      违规告警
      <el-badge v-if="mapStore.alerts.length" :value="mapStore.alerts.length" :max="99" class="alert-badge" />
      <el-button
        v-if="mapStore.alerts.length"
        link
        size="small"
        type="danger"
        style="margin-left: auto;"
        @click="mapStore.clearAlerts()"
      >
        清空
      </el-button>
    </div>

    <div v-if="mapStore.alerts.length === 0" class="empty-hint">
      暂无违规告警
    </div>

    <el-scrollbar max-height="240px" v-else>
      <div class="alert-list">
        <div
          v-for="alert in mapStore.alerts"
          :key="alert.id"
          class="alert-item"
        >
          <div class="alert-icon">
            <el-icon color="#ef4444"><WarningFilled /></el-icon>
          </div>
          <div class="alert-content">
            <div class="alert-main">
              <span class="alert-class">{{ alert.class_name }}</span>
              <span class="alert-tid">#{{ alert.track_id }}</span>
              <span class="alert-arrow">→</span>
              <span class="alert-zone">{{ alert.zoneName }}</span>
            </div>
            <div class="alert-time">{{ formatTime(alert.timestamp) }}</div>
          </div>
        </div>
      </div>
    </el-scrollbar>
  </div>
</template>

<script setup lang="ts">
import { Warning, WarningFilled } from '@element-plus/icons-vue'
import { useMapStore } from '@/stores/map'

const mapStore = useMapStore()

function formatTime(ts: number): string {
  return new Date(ts).toLocaleTimeString()
}
</script>

<style lang="scss" scoped>
.panel-section {
  padding: 16px;
  border-bottom: 1px solid $border-color;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 700;
  color: $text-primary;
  margin-bottom: 12px;
}

.alert-badge {
  margin-left: 4px;
}

.empty-hint {
  font-size: 13px;
  color: $text-muted;
  text-align: center;
  padding: 12px 0;
}

.alert-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.alert-item {
  display: flex;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 8px;
  background: rgba(239, 68, 68, 0.04);
  border: 1px solid rgba(239, 68, 68, 0.1);
  animation: slideIn 0.3s ease;
}

.alert-icon {
  flex-shrink: 0;
  padding-top: 2px;
}

.alert-content {
  flex: 1;
  min-width: 0;
}

.alert-main {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  flex-wrap: wrap;
}

.alert-class {
  font-weight: 600;
  color: $text-primary;
}

.alert-tid {
  color: $text-muted;
  font-size: 12px;
}

.alert-arrow {
  color: $text-muted;
}

.alert-zone {
  color: #ef4444;
  font-weight: 600;
}

.alert-time {
  font-size: 11px;
  color: $text-muted;
  margin-top: 2px;
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateX(10px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}
</style>
