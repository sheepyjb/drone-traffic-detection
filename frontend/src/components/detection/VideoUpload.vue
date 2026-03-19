<template>
  <div class="ind-upload">
    <div class="upload-drop" :class="{ dragging }" @dragover.prevent="dragging = true" @dragleave="dragging = false" @drop.prevent="handleDrop" @click="triggerInput">
      <div class="upload-icon"><el-icon :size="20"><UploadFilled /></el-icon></div>
      <div class="upload-text">
        <span class="ut-main">{{ label }}</span>
        <span class="ut-hint">{{ accept.includes('video') ? 'MP4 / AVI / MOV / JPG / PNG' : 'JPG / PNG' }}</span>
      </div>
    </div>
    <input ref="inputRef" type="file" :accept="accept" class="hidden" @change="handleFileChange" />

    <div v-if="fileName" class="file-pill">
      <span>{{ fileName }}</span>
      <span class="remove" @click="clearFile">&times;</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { UploadFilled } from '@element-plus/icons-vue'

const props = withDefaults(defineProps<{
  label?: string
  accept?: string
}>(), {
  label: '拖拽或点击上传',
  accept: 'video/mp4,video/avi,video/quicktime,image/jpeg,image/png,.mp4,.avi,.mov,.jpg,.png',
})

const emit = defineEmits<{ upload: [file: File] }>()
const inputRef = ref<HTMLInputElement | null>(null)
const dragging = ref(false)
const fileName = ref('')

let pendingFile: File | null = null

function triggerInput() { inputRef.value?.click() }

function handleFileChange(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (file) { pendingFile = file; fileName.value = file.name; emit('upload', file) }
}
function handleDrop(e: DragEvent) {
  dragging.value = false
  const file = e.dataTransfer?.files[0]
  if (file) { pendingFile = file; fileName.value = file.name; emit('upload', file) }
}

function clearFile() {
  fileName.value = ''
  pendingFile = null
  if (inputRef.value) inputRef.value.value = ''
}
</script>

<style lang="scss" scoped>
.ind-upload { display: flex; flex-direction: column; gap: 8px; flex: 1; }
.upload-drop {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 18px;
  background: $bg-card-alt;
  border: 1px dashed rgba(0, 0, 0, 0.15);
  border-radius: $radius-md;
  cursor: pointer;
  transition: all $transition-fast;
  &:hover, &.dragging {
    border-color: $ind-cyan;
    background: rgba(8, 145, 178, 0.04);
  }
}
.upload-icon {
  width: 42px; height: 42px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba($ind-amber, 0.1);
  color: $ind-amber;
  border: 1px solid rgba($ind-amber, 0.25);
  border-radius: $radius-sm;
}
.upload-text { display: flex; flex-direction: column; }
.ut-main { font-size: 14px; font-weight: 600; color: $text-primary; }
.ut-hint { font-size: 11px; color: $text-muted; margin-top: 2px; }
.hidden { display: none; }
.file-pill {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 13px;
  font-family: $font-mono;
  color: $text-secondary;
  background: $bg-card-alt;
  padding: 8px 14px;
  border-radius: $radius-sm;
  border: 1px solid $border-color;
  .remove { cursor: pointer; font-size: 18px; color: $text-muted; &:hover { color: $ind-red; } }
}
</style>
