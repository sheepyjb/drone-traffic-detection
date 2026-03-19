import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { ModelInfo } from '@/types'
import { useDetectionStore } from '@/stores/detection'

export const useAppStore = defineStore('app', () => {
  const currentModel = ref('')
  const wsConnected = ref(false)
  const sidebarCollapsed = ref(false)
  const modelSwitching = ref(false)

  const availableModels = ref<ModelInfo[]>([])
  let modelsRetryTimer: ReturnType<typeof setTimeout> | null = null

  function scheduleFetchModelsRetry() {
    if (modelsRetryTimer) return
    modelsRetryTimer = setTimeout(() => {
      modelsRetryTimer = null
      void fetchModels()
    }, 3000)
  }

  async function fetchModels() {
    try {
      const res = await fetch('/api/models')
      if (!res.ok) {
        scheduleFetchModelsRetry()
        return
      }
      const data = await res.json()
      const models: ModelInfo[] = (data.models || [])
        .filter((m: { exists: boolean }) => m.exists)
        .map((m: { id: string; path: string; active: boolean }) => ({
          id: m.id,
          name: m.id,
          description: m.path,
          params: '-',
          gflops: 0,
          map50: 0,
          fps: 0,
        }))
      availableModels.value = models
      const active = (data.models || []).find((m: { active: boolean }) => m.active)
      if (active) currentModel.value = active.id
      if (modelsRetryTimer) {
        clearTimeout(modelsRetryTimer)
        modelsRetryTimer = null
      }
    } catch {
      scheduleFetchModelsRetry()
    }
  }

  async function setModel(modelId: string) {
    if (modelSwitching.value) return
    modelSwitching.value = true
    try {
      const form = new FormData()
      form.append('model_id', modelId)
      const res = await fetch('/api/models/switch', { method: 'POST', body: form })
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: '切换失败' }))
        throw new Error(err.detail || '切换失败')
      }
      currentModel.value = modelId
      const detectionStore = useDetectionStore()
      await detectionStore.fetchCategories()
    } finally {
      modelSwitching.value = false
    }
  }

  const isFusionModel = computed(() => currentModel.value === 'yolo26s-fusion')

  function toggleSidebar() {
    sidebarCollapsed.value = !sidebarCollapsed.value
  }

  return {
    currentModel, wsConnected, sidebarCollapsed, availableModels, modelSwitching, isFusionModel,
    fetchModels, setModel, toggleSidebar,
  }
})
