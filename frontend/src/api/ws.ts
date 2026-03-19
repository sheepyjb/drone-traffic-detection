import type { WsMessage } from '@/types'

type MessageHandler = (msg: WsMessage) => void

export class WsClient {
  private ws: WebSocket | null = null
  private url: string
  private handlers: MessageHandler[] = []
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private maxRetries = 5
  private retryCount = 0
  private retryDelay = 2000

  constructor(url: string) {
    this.url = url
  }

  connect() {
    if (this.ws?.readyState === WebSocket.OPEN) return

    try {
      this.ws = new WebSocket(this.url)

      this.ws.onopen = () => {
        console.log('[WS] Connected')
        this.retryCount = 0
      }

      this.ws.onmessage = (event) => {
        try {
          const msg: WsMessage = JSON.parse(event.data)
          this.handlers.forEach(h => h(msg))
        } catch (e) {
          console.warn('[WS] Parse error', e)
        }
      }

      this.ws.onclose = () => {
        console.log('[WS] Disconnected')
        this.scheduleReconnect()
      }

      this.ws.onerror = (err) => {
        console.error('[WS] Error', err)
        this.ws?.close()
      }
    } catch {
      this.scheduleReconnect()
    }
  }

  private scheduleReconnect() {
    if (this.retryCount >= this.maxRetries) return
    if (this.reconnectTimer) return

    this.retryCount++
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null
      this.connect()
    }, this.retryDelay * this.retryCount)
  }

  onMessage(handler: MessageHandler) {
    this.handlers.push(handler)
  }

  send(data: unknown) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data))
    }
  }

  disconnect() {
    this.maxRetries = 0
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    this.ws?.close()
    this.ws = null
  }

  get connected() {
    return this.ws?.readyState === WebSocket.OPEN
  }
}
