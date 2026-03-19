import { ref, onUnmounted, type Ref } from 'vue'
import AMapLoader from '@amap/amap-jsapi-loader'

// 安全密钥
;(window as any)._AMapSecurityConfig = {
  securityJsCode: '91fca21a13b831c405738c2977d2130b',
}

const AMAP_KEY = 'd82c2bbd409f4cc49f97915906f66773'

let AMapRef: any = null
let loadPromise: Promise<any> | null = null

function loadAMap() {
  if (AMapRef) return Promise.resolve(AMapRef)
  if (!loadPromise) {
    loadPromise = AMapLoader.load({
      key: AMAP_KEY,
      version: '2.0',
    }).then((AMap: any) => {
      AMapRef = AMap
      return AMap
    })
  }
  return loadPromise
}

export function useAMap(containerId: string) {
  const map: Ref<any> = ref(null)
  const AMap: Ref<any> = ref(null)
  const ready = ref(false)

  async function initMap(center: [number, number] = [120.1, 30.271], zoom = 17) {
    const _AMap = await loadAMap()
    AMap.value = _AMap

    const mapInstance = new _AMap.Map(containerId, {
      center,
      zoom,
      viewMode: '2D',
      mapStyle: 'amap://styles/normal',
      features: ['bg', 'road', 'building', 'point'],
    })

    map.value = mapInstance
    ready.value = true
    return mapInstance
  }

  onUnmounted(() => {
    if (map.value) {
      map.value.destroy()
      map.value = null
    }
  })

  return { map, AMap, ready, initMap }
}
