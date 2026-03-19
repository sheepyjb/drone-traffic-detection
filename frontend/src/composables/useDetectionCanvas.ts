import { ref, onUnmounted } from 'vue'
import type { Track } from '@/types'
import { useDetectionStore } from '@/stores/detection'

export function useDetectionCanvas() {
  const canvasRef = ref<HTMLCanvasElement | null>(null)
  let animationId = 0
  const detectionStore = useDetectionStore()

  function drawDetections(tracks: Track[], frameImage?: HTMLImageElement | HTMLVideoElement | ImageBitmap) {
    const canvas = canvasRef.value
    if (!canvas) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const w = canvas.width
    const h = canvas.height

    ctx.clearRect(0, 0, w, h)

    if (frameImage) {
      ctx.drawImage(frameImage, 0, 0, w, h)
    }

    for (const track of tracks) {
      const color = detectionStore.categoryColorMap[track.class_id] || '#06b6d4'
      const [x1, y1, x2, y2] = track.bbox
      const bx = x1 * w
      const by = y1 * h
      const bw = (x2 - x1) * w
      const bh = (y2 - y1) * h

      // 绘制 mask 多边形（半透明填充）
      if (track.mask && track.mask.length >= 3) {
        ctx.save()
        ctx.globalAlpha = 0.3
        ctx.fillStyle = color
        ctx.beginPath()
        ctx.moveTo(track.mask[0][0] * w, track.mask[0][1] * h)
        for (let i = 1; i < track.mask.length; i++) {
          ctx.lineTo(track.mask[i][0] * w, track.mask[i][1] * h)
        }
        ctx.closePath()
        ctx.fill()
        ctx.restore()

        // mask 轮廓线
        ctx.strokeStyle = color
        ctx.lineWidth = 1.5
        ctx.beginPath()
        ctx.moveTo(track.mask[0][0] * w, track.mask[0][1] * h)
        for (let i = 1; i < track.mask.length; i++) {
          ctx.lineTo(track.mask[i][0] * w, track.mask[i][1] * h)
        }
        ctx.closePath()
        ctx.stroke()
      }

      // 检测框
      ctx.strokeStyle = color
      ctx.lineWidth = 2
      ctx.strokeRect(bx, by, bw, bh)

      // 角标
      const cornerLen = Math.min(10, bw * 0.15, bh * 0.15)
      ctx.lineWidth = 2.5
      ctx.beginPath()
      ctx.moveTo(bx, by + cornerLen); ctx.lineTo(bx, by); ctx.lineTo(bx + cornerLen, by)
      ctx.moveTo(bx + bw - cornerLen, by); ctx.lineTo(bx + bw, by); ctx.lineTo(bx + bw, by + cornerLen)
      ctx.moveTo(bx + bw, by + bh - cornerLen); ctx.lineTo(bx + bw, by + bh); ctx.lineTo(bx + bw - cornerLen, by + bh)
      ctx.moveTo(bx + cornerLen, by + bh); ctx.lineTo(bx, by + bh); ctx.lineTo(bx, by + bh - cornerLen)
      ctx.stroke()

      // 标签
      const classInfo = detectionStore.categories.find(c => c.id === track.class_id)
      const label = `#${track.track_id} ${classInfo?.label || track.class_name} ${(track.confidence * 100).toFixed(0)}%`
      ctx.font = '600 12px "Inter", "Microsoft YaHei", sans-serif'
      const textWidth = ctx.measureText(label).width
      const labelH = 20
      const labelY = by > labelH + 2 ? by - labelH - 2 : by

      ctx.fillStyle = 'rgba(0, 0, 0, 0.75)'
      ctx.beginPath()
      ctx.roundRect(bx, labelY, textWidth + 10, labelH, 3)
      ctx.fill()

      // 标签左侧色条
      ctx.fillStyle = color
      ctx.fillRect(bx, labelY, 3, labelH)

      ctx.fillStyle = '#e2e8f0'
      ctx.fillText(label, bx + 7, labelY + 14)
    }
  }

  function resizeCanvas(width: number, height: number) {
    if (!canvasRef.value) return
    canvasRef.value.width = width
    canvasRef.value.height = height
  }

  function captureCanvas(): string | null {
    const canvas = canvasRef.value
    if (!canvas) return null
    return canvas.toDataURL('image/png')
  }

  onUnmounted(() => {
    if (animationId) cancelAnimationFrame(animationId)
  })

  return { canvasRef, drawDetections, resizeCanvas, captureCanvas }
}
