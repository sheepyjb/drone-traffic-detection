<template>
  <div class="panel-section">
    <div class="section-title">
      <el-icon><DataAnalysis /></el-icon>
      目标统计
    </div>

    <!-- 分类统计 -->
    <div class="stats-grid">
      <div
        v-for="cat in detectionStore.categories"
        :key="cat.id"
        class="stat-card"
        :class="{ warning: isOverThreshold(cat.id) }"
      >
        <div class="stat-color" :style="{ background: cat.color }"></div>
        <div class="stat-info">
          <span class="stat-label">{{ cat.label }}</span>
          <span class="stat-count">{{ getCount(cat.id) }}</span>
        </div>
        <div v-if="isOverThreshold(cat.id)" class="stat-warn">
          <el-icon color="#ef4444"><WarningFilled /></el-icon>
        </div>
      </div>
    </div>

    <!-- 阈值告警 -->
    <div v-if="mapStore.thresholdAlerts.length > 0" class="threshold-alerts">
      <div class="alert-header">
        <el-icon color="#ef4444"><Bell /></el-icon>
        <span>阈值告警</span>
      </div>
      <div v-for="ta in mapStore.thresholdAlerts" :key="ta.classId" class="threshold-item">
        <span>{{ ta.className }}</span>
        <el-tag type="danger" size="small">{{ ta.count }} / {{ ta.threshold }}</el-tag>
      </div>
    </div>

    <!-- 阈值设置 -->
    <el-collapse>
      <el-collapse-item title="阈值设置" name="thresholds">
        <div class="threshold-grid">
          <div v-for="th in mapStore.thresholds" :key="th.classId" class="threshold-row">
            <span class="th-label">{{ getCategoryLabel(th.classId) }}</span>
            <el-input-number
              v-model="th.threshold"
              :min="1"
              :max="100"
              size="small"
              controls-position="right"
            />
          </div>
        </div>
      </el-collapse-item>
    </el-collapse>
  </div>
</template>

<script setup lang="ts">
import { DataAnalysis, WarningFilled, Bell } from '@element-plus/icons-vue'
import { useDetectionStore } from '@/stores/detection'
import { useMapStore } from '@/stores/map'

const detectionStore = useDetectionStore()
const mapStore = useMapStore()

function getCount(classId: number): number {
  return detectionStore.categoryCounts[classId] || 0
}

function isOverThreshold(classId: number): boolean {
  return mapStore.thresholdAlerts.some((a) => a.classId === classId)
}

function getCategoryLabel(classId: number): string {
  return detectionStore.categories.find((c) => c.id === classId)?.label || `类别${classId}`
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

.stats-grid {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border-radius: 8px;
  background: rgba(0, 0, 0, 0.02);
  border: 1px solid transparent;
  transition: all 0.2s;

  &.warning {
    background: rgba(239, 68, 68, 0.06);
    border-color: rgba(239, 68, 68, 0.2);
    animation: pulse-warn 1.5s infinite;
  }
}

.stat-color {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}

.stat-info {
  flex: 1;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.stat-label {
  font-size: 13px;
  color: $text-secondary;
}

.stat-count {
  font-size: 15px;
  font-weight: 700;
  color: $text-primary;
  font-variant-numeric: tabular-nums;
}

.stat-warn {
  flex-shrink: 0;
}

.threshold-alerts {
  margin-top: 10px;
  padding: 8px 10px;
  background: rgba(239, 68, 68, 0.05);
  border-radius: 8px;
  border: 1px solid rgba(239, 68, 68, 0.15);
}

.alert-header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  color: #ef4444;
  margin-bottom: 6px;
}

.threshold-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 0;
  font-size: 12px;
  color: $text-secondary;
}

.threshold-grid {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.threshold-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;

  .th-label {
    font-size: 12px;
    color: $text-secondary;
    min-width: 60px;
  }

  .el-input-number {
    width: 110px;
  }
}

@keyframes pulse-warn {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
}
</style>
