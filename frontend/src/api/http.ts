import axios from 'axios'

const http = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

http.interceptors.response.use(
  (res) => res.data,
  (err) => {
    console.error('[HTTP Error]', err.message)
    return Promise.reject(err)
  }
)

export default http

// API 方法 — 后端就绪后对接
export const api = {
  // 上传视频
  uploadVideo: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return http.post('/detect/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  // 获取模型列表
  getModels: () => http.get('/models'),
  // 获取评估指标
  getMetrics: (modelId: string) => http.get(`/metrics/${modelId}`),
  // 开始检测
  startDetect: (params: { model: string; source: string }) => http.post('/detect/start', params),
  // 停止检测
  stopDetect: () => http.post('/detect/stop'),
}
