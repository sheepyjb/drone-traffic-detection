import { ref, onUnmounted } from 'vue'
import { WsClient } from '@/api/ws'
import { useDetectionStore } from '@/stores/detection'
import { useAppStore } from '@/stores/app'

export function useWebSocket(url = `ws://${location.host}/ws/detect`) {
  const client = ref<WsClient | null>(null)
  const detectionStore = useDetectionStore()
  const appStore = useAppStore()

  function connect() {
    client.value = new WsClient(url)
    client.value.onMessage((msg) => {
      if (msg.type === 'detection') {
        detectionStore.updateDetection(
          msg.frame, msg.tracks, msg.fps, msg.latency_ms, msg.frame_id
        )
      } else if (msg.type === 'status') {
        appStore.wsConnected = msg.connected
      }
    })
    client.value.connect()
    appStore.wsConnected = true
  }

  function disconnect() {
    client.value?.disconnect()
    client.value = null
    appStore.wsConnected = false
  }

  function send(data: unknown) {
    client.value?.send(data)
  }

  onUnmounted(() => disconnect())

  return { connect, disconnect, send, client }
}
