<template>
  <div class="panel-section">
    <div class="section-title">
      <el-icon><Bell /></el-icon>
      事件预警
      <el-badge v-if="dangerCount > 0" :value="dangerCount" type="danger" class="event-badge" />
      <el-badge v-else-if="warningCount > 0" :value="warningCount" type="warning" class="event-badge" />
      <el-button
        v-if="flowCountStore.trafficEvents.length"
        link
        size="small"
        type="danger"
        style="margin-left: auto;"
        @click="flowCountStore.clearEvents()"
      >
        清空
      </el-button>
    </div>

    <div v-if="flowCountStore.trafficEvents.length === 0" class="empty-hint">
      暂无交通事件
    </div>

    <el-scrollbar max-height="260px" v-else>
      <div class="event-list">
        <div
          v-for="event in flowCountStore.trafficEvents"
          :key="event.id"
          class="event-item"
          :class="event.severity"
        >
          <div class="event-icon">
            <span class="severity-dot" :class="event.severity"></span>
          </div>
          <div class="event-content">
            <div class="event-type">
              <el-tag :type="eventTagType(event.type)" size="small" effect="plain">
                {{ eventTypeLabel(event.type) }}
              </el-tag>
            </div>
            <div class="event-msg">{{ event.message }}</div>
            <div class="event-time">{{ formatTime(event.timestamp) }}</div>
          </div>
        </div>
      </div>
    </el-scrollbar>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Bell } from '@element-plus/icons-vue'
import { useFlowCountStore } from '@/stores/flowCount'

const flowCountStore = useFlowCountStore()

const dangerCount = computed(() =>
  flowCountStore.trafficEvents.filter(e => e.severity === 'danger').length
)
const warningCount = computed(() =>
  flowCountStore.trafficEvents.filter(e => e.severity === 'warning').length
)

function eventTypeLabel(type: string): string {
  const map: Record<string, string> = {
    wrong_way: '逆行',
    illegal_stop: '违停',
    long_queue: '长排队',
    accident_suspect: '疑似事故',
  }
  return map[type] || type
}

function eventTagType(type: string) {
  if (type === 'accident_suspect' || type === 'wrong_way') return 'danger'
  if (type === 'long_queue') return 'warning'
  return 'info'
}

function formatTime(ts: number): string {
  return new Date(ts).toLocaleTimeString('zh-CN', {
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  })
}
</script>

<style lang="scss" scoped>
.panel-section {
  padding: 16px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
}

.section-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 700;
  color: #1e293b;
  margin-bottom: 12px;
}

.event-badge {
  margin-left: 4px;
}

.empty-hint {
  font-size: 13px;
  color: #94a3b8;
  text-align: center;
  padding: 12px 0;
}

.event-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.event-item {
  display: flex;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 8px;
  animation: slideIn 0.3s ease;

  &.danger {
    background: rgba(239, 68, 68, 0.05);
    border: 1px solid rgba(239, 68, 68, 0.12);
  }
  &.warning {
    background: rgba(245, 158, 11, 0.05);
    border: 1px solid rgba(245, 158, 11, 0.12);
  }
}

.event-icon {
  flex-shrink: 0;
  padding-top: 4px;
}

.severity-dot {
  display: block;
  width: 8px;
  height: 8px;
  border-radius: 50%;

  &.danger {
    background: #ef4444;
    box-shadow: 0 0 6px rgba(239, 68, 68, 0.5);
    animation: pulse 1.5s infinite;
  }
  &.warning {
    background: #f59e0b;
    box-shadow: 0 0 6px rgba(245, 158, 11, 0.4);
  }
}

.event-content {
  flex: 1;
  min-width: 0;
}

.event-type {
  margin-bottom: 3px;
}

.event-msg {
  font-size: 12px;
  color: #334155;
  line-height: 1.4;
}

.event-time {
  font-size: 10px;
  color: #94a3b8;
  margin-top: 2px;
  font-family: 'JetBrains Mono', monospace;
}

@keyframes slideIn {
  from { opacity: 0; transform: translateX(10px); }
  to { opacity: 1; transform: translateX(0); }
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
</style>
