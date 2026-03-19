<template>
  <div class="clay-model-select">
    <span class="select-tag">模型</span>
    <el-select
      v-model="appStore.currentModel"
      size="small"
      style="width: 210px"
      :loading="appStore.modelSwitching"
      :disabled="appStore.modelSwitching"
      @change="handleSwitch"
    >
      <el-option v-for="m in appStore.availableModels" :key="m.id" :label="m.name" :value="m.id">
        <div class="m-opt"><span>{{ m.name }}</span><span class="m-meta mono">{{ m.params }}</span></div>
      </el-option>
    </el-select>
  </div>
</template>

<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { useAppStore } from '@/stores/app'

const appStore = useAppStore()

async function handleSwitch(modelId: string) {
  try {
    await appStore.setModel(modelId)
    ElMessage.success(`已切换到 ${modelId}`)
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : '切换失败'
    ElMessage.error(msg)
  }
}
</script>

<style lang="scss" scoped>
.clay-model-select { display: flex; align-items: center; gap: 10px; }
.select-tag { font-size: 13px; font-weight: 700; color: $text-secondary; }
.m-opt { display: flex; justify-content: space-between; width: 100%; }
.m-meta { font-size: 11px; color: $text-muted; }
</style>
