<script setup lang="ts">
import { computed, onMounted, ref, h, watch, nextTick } from 'vue'
import * as echarts from 'echarts'
import VChart from 'vue-echarts'
import { PlayCircleOutlined, StopOutlined, DollarOutlined, EnvironmentOutlined, FieldTimeOutlined, CarOutlined, DashboardOutlined, InboxOutlined, HourglassOutlined, CoffeeOutlined, StepBackwardOutlined, StepForwardOutlined, UploadOutlined, BookOutlined, UserOutlined } from '@ant-design/icons-vue'
import { theme, message } from 'ant-design-vue'
import 'mapbox-gl/dist/mapbox-gl.css'
import mapboxgl from 'mapbox-gl'

const mapContainer = ref<HTMLElement | null>(null)
const mapboxContainer = ref<HTMLElement | null>(null)
let mainMapChart: any = null
let mapboxMapInstance: mapboxgl.Map | null = null
const isGeoMode = ref(false)
let currentProblemFitted = false

const problems = ref<any[]>([])
const selectedProblem = ref<string | null>(null)
const maxTime = ref<number>(60)
const maxGen = ref<number>(3000)
const mapboxToken = ref(localStorage.getItem('mapboxToken') || '')

watch(mapboxToken, (newVal) => {
  if (newVal) {
    localStorage.setItem('mapboxToken', newVal)
  } else {
    localStorage.removeItem('mapboxToken')
  }
})

const runData = ref<any>({ history: [] })
const loading = ref(false)
const running = ref(false)
const currentHistoryIndex = ref(0)
const localElapsedSeconds = ref<number>(0)
let timerInterval: any = null
let ws: WebSocket | null = null

const fetchProblems = async () => {
  try {
    const res = await fetch('/api/problems')
    const data = await res.json()
    problems.value = data.problems
    if (problems.value.length > 0 && !selectedProblem.value) {
      selectedProblem.value = problems.value[0].path
    }
  } catch (error) {
    console.error('Failed to fetch problems.', error)
  }
}

const startSolver = () => {
  if (!selectedProblem.value) return
  if (ws) {
    ws.close()
  }
  
  if (runData.value.history && runData.value.history.length > 0) {
    runData.value.history = [runData.value.history[0]]
  } else {
    runData.value = { history: [] }
  }
  currentHistoryIndex.value = 0
  running.value = true
  
  localElapsedSeconds.value = 0
  if (timerInterval) clearInterval(timerInterval)
  timerInterval = setInterval(() => {
    localElapsedSeconds.value += 0.1
  }, 100)
  
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  ws = new WebSocket(`${protocol}//${window.location.host}/ws/solve`)
  
  ws.onopen = () => {
    const p = problems.value.find(p => p.path === selectedProblem.value)
    ws?.send(JSON.stringify({
      action: 'start',
      problem_path: p.path,
      matrix_path: p.matrix_path,
      max_time: maxTime.value,
      max_gen: maxGen.value
    }))
  }
  
  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data)
    if (msg.type === 'time') {
      localElapsedSeconds.value = msg.data.elapsed_seconds
    } else if (msg.type === 'metadata') {
      runData.value.jobs_meta = msg.data
    } else if (msg.type === 'iteration') {
      if (msg.data.elapsed_seconds !== undefined) {
        localElapsedSeconds.value = msg.data.elapsed_seconds
      }
      runData.value.history.push(msg.data)
      currentHistoryIndex.value = runData.value.history.length - 1
    } else if (msg.type === 'finished' || msg.type === 'error') {
      running.value = false
      if (timerInterval) clearInterval(timerInterval)
      if (msg.type === 'error') {
        console.error("Solver error:", msg.message)
        message.error({ content: "Solver error: " + msg.message, duration: 5 })
      }
    }
  }
  
  ws.onclose = () => {
    running.value = false
    if (timerInterval) clearInterval(timerInterval)
  }
}

const stopSolver = () => {
  if (ws) {
    ws.close()
    ws = null
  }
  running.value = false
  if (timerInterval) clearInterval(timerInterval)
}

const fetchInitialState = async (path?: string) => {
  const targetPath = path || selectedProblem.value
  if (!targetPath) return
  try {
    const res = await fetch('/api/problem/initial_state', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ problem_path: targetPath })
    })
    const data = await res.json()
    if (data.initial_state) {
      runData.value = {
        jobs_meta: data.jobs_meta,
        history: [{
          generation: 0,
          cost: 0,
          tours: data.initial_state.tours,
          unassigned: data.initial_state.unassigned
        }]
      }
      currentHistoryIndex.value = 0
    }
  } catch (error) {
    console.error('Failed to fetch initial state', error)
  }
}

watch(selectedProblem, (newVal) => {
  currentProblemFitted = false
  if (newVal && !running.value) {
    fetchInitialState(newVal)
  }
})

const handleUploadChange = (info: any) => {
  if (info.file.status === 'done') {
    message.success(`${info.file.name} file uploaded successfully`)
    fetchProblems().then(() => {
      if (info.file.response && info.file.response.problem_path) {
        selectedProblem.value = info.file.response.problem_path
        fetchInitialState()
      }
    })
  } else if (info.file.status === 'error') {
    message.error(`${info.file.name} file upload failed: ${info.file.response?.error || 'Unknown error'}`)
  }
}

const jumpToPreviousSolution = () => {
  if (!runData.value?.history?.length) return
  currentHistoryIndex.value = Math.max(currentHistoryIndex.value - 1, 0)
}

const jumpToNextSolution = () => {
  if (!runData.value?.history?.length) return
  currentHistoryIndex.value = Math.min(currentHistoryIndex.value + 1, runData.value.history.length - 1)
}

const currentStats = computed(() => {
  if (!runData.value?.history?.length) return null
  return runData.value.history[currentHistoryIndex.value]
})

const currentSnapshot = computed(() => currentStats.value)

const latestBest = computed(() => {
  if (!runData.value?.history?.length) return null
  const validHistory = runData.value.history.filter((item: any) => !(item.generation === 0 && item.cost === 0))
  if (validHistory.length === 0) return null
  return [...validHistory].sort((a: any, b: any) => a.cost - b.cost)[0]
})

const jobsMeta = computed<Record<string, any>>(() => runData.value?.jobs_meta ?? {})

const fmtSecs = (s: number | undefined | null): string => {
  if (s === undefined || s === null || Number.isNaN(s)) return 'N/A'
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = s % 60
  if (h > 0) return `${h}h ${m}m`
  if (m > 0) return `${m}m ${sec}s`
  return `${sec}s`
}

const fmtCoord = (v: number | undefined | null): string =>
  v === undefined || v === null || Number.isNaN(v) ? 'N/A' : Number(v).toFixed(5)

const colors = ['#8b5cf6', '#38bdf8', '#34d399', '#f59e0b', '#f472b6', '#22d3ee', '#fb7185', '#a78bfa']

const convergenceChartOption = computed(() => {
  if (!runData.value?.history?.length || !currentSnapshot.value) return {}

  const history = runData.value.history
  const chartHistory = history.filter((item: any) => !(item.generation === 0 && item.cost === 0))
  const xData = chartHistory.map((item: any) => item.generation)
  const costData = chartHistory.map((item: any) => item.cost)
  const currentItem = history[currentHistoryIndex.value]
  const chartCurrentIndex = chartHistory.indexOf(currentItem)

  return {
    animation: false,
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(15, 23, 42, 0.95)',
      borderColor: 'rgba(99, 102, 241, 0.35)',
      textStyle: { color: '#f8fafc' }
    },
    grid: { left: 24, right: 12, top: 12, bottom: 32 },
    xAxis: {
      type: 'category',
      data: xData,
      name: 'Generation',
      nameLocation: 'middle',
      nameGap: 26,
      nameTextStyle: { color: '#cbd5e1' },
      axisLine: { lineStyle: { color: '#334155' } },
      axisLabel: { color: '#94a3b8', fontSize: 11 }
    },
    yAxis: {
      type: 'value',
      scale: true,
      axisLine: { show: false },
      splitLine: { lineStyle: { color: 'rgba(148, 163, 184, 0.12)' } },
      axisLabel: { color: '#94a3b8', fontSize: 11 }
    },
    series: [
      {
        name: 'Cost',
        type: 'line',
        smooth: true,
        showSymbol: true,
        symbol: 'circle',
        symbolSize: (_value: any, params: any) => params.dataIndex === chartCurrentIndex ? 18 : 0,
        itemStyle: {
          color: '#f59e0b'
        },
        emphasis: {
          focus: 'series'
        },
        data: costData,
        lineStyle: { color: '#8b5cf6', width: 2.6 },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(139, 92, 246, 0.32)' },
              { offset: 1, color: 'rgba(139, 92, 246, 0)' }
            ]
          }
        }
      }
    ]
  }
})

const vehicleColorMap = new Map<string, string>()
let nextColorIndex = 0
const getVehicleColor = (vehicleId: string) => {
  if (!vehicleColorMap.has(vehicleId)) {
    vehicleColorMap.set(vehicleId, colors[nextColorIndex % colors.length])
    nextColorIndex++
  }
  return vehicleColorMap.get(vehicleId) as string
}

const mapChartOption = computed(() => {
  if (!runData.value?.history?.length || !currentSnapshot.value) return {}

  const currentStep = currentSnapshot.value
  if (!currentStep?.tours) {
    return {
      backgroundColor: 'transparent',
      title: {
        text: 'No route data for this generation',
        left: 'center',
        top: 'center',
        textStyle: { color: '#cbd5e1', fontSize: 16 }
      }
    }
  }

  const series: any[] = []
  let hasValidCoords = false

  let isGeo = false
  let isIndex = false
  
  let sumLng = 0, sumLat = 0, ptCount = 0

  currentStep.tours.forEach((tour: any) => {
    if (tour.stops && tour.stops.length > 0) {
      const loc = tour.stops[0].location
      if (loc?.lng !== undefined && loc?.lat !== undefined) {
        isGeo = true
        isGeoMode.value = true
      }
      else if (loc?.index !== undefined) isIndex = true
    }
  })

  // Since Mapbox GL handles geo-rendering natively now, we bypass ECharts entirely for geo problems.
  if (isGeo) {
    return {}
  }

  const graphNodes = new Map<string, any>()
  const graphLinks: any[] = []

  currentStep.tours.forEach((tour: any) => {
    const color = getVehicleColor(tour.vehicleId)
    const coords: [number, number][] = []
    const scatterData: any[] = []
    let prevNodeId: string | null = null

    tour.stops.forEach((stop: any, stopIndex: number) => {
      const hasGeo = stop.location?.lng !== undefined && stop.location?.lat !== undefined
      const hasIdx = stop.location?.index !== undefined
      if (!hasGeo && !hasIdx) return
      
      hasValidCoords = true
      const activities = stop.activities || []
      const primaryActivity = activities[0]
      const jobId: string = primaryActivity?.jobId ?? ''
      const pointLabel = jobId || primaryActivity?.type || `Stop ${stopIndex + 1}`

      const fmtLoad = (load: unknown): string => {
        if (Array.isArray(load)) return load.length ? load.join(', ') : 'N/A'
        return load === undefined || load === null ? 'N/A' : String(load)
      }

      const actualSvcSecs = (() => {
        const arr = Date.parse(stop.time?.arrival)
        const dep = Date.parse(stop.time?.departure)
        if (!stop?.time?.arrival || !stop?.time?.departure || isNaN(arr) || isNaN(dep)) return null
        return Math.round((dep - arr) / 1000)
      })()

      const jm = jobsMeta.value[jobId]
      const place0 = jm?.places?.[0]
      const plannedSvcSecs: number | undefined = place0?.duration
      const timeWindows: any[][] | undefined = place0?.times
      const twStr = timeWindows?.length
        ? timeWindows.map((tw: any[]) => `${tw[0]} – ${tw[1]}`).join(', ')
        : undefined
        
      const skillsObj = jm?.skills
      let skillsStr = '—'
      if (skillsObj) {
         const parts = []
         if (skillsObj.allOf?.length) parts.push(`All: ${skillsObj.allOf.join(', ')}`)
         if (skillsObj.anyOf?.length) parts.push(`Any: ${skillsObj.anyOf.join(', ')}`)
         if (skillsObj.noneOf?.length) parts.push(`None: ${skillsObj.noneOf.join(', ')}`)
         if (parts.length) skillsStr = parts.join(' | ')
      }
      
      let shape = 'circle'
      let size = 8
      switch (primaryActivity?.type) {
        case 'departure':
        case 'arrival':
        case 'depot':
          shape = 'rect'
          size = 12
          break
        case 'pickup':
          shape = 'triangle'
          size = 10
          break
        case 'delivery':
          shape = 'circle'
          size = 8
          break
        case 'recharge':
          shape = 'diamond'
          size = 12
          break
        case 'break':
          shape = 'roundRect'
          size = 10
          break
        default:
          shape = 'circle'
          size = 8
          break
      }
      
      const stopMeta = {
        jobId,
        pointLabel,
        actType: primaryActivity?.type || 'stop',
        vehicleId: tour.vehicleId,
        lat: hasGeo ? stop.location.lat : 'N/A',
        lng: hasGeo ? stop.location.lng : 'N/A',
        arrival: stop.time?.arrival || 'N/A',
        departure: stop.time?.departure || 'N/A',
        actualSvc: actualSvcSecs !== null ? fmtSecs(actualSvcSecs) : 'N/A',
        plannedSvc: plannedSvcSecs !== undefined ? fmtSecs(plannedSvcSecs) : '—',
        timeWindows: twStr ?? '—',
        distance: stop.distance ?? 'N/A',
        load: fmtLoad(stop.load),
        skills: skillsStr,
      }

      if (isIndex && hasIdx) {
        const nodeId = `loc_${stop.location.index}`
        const isDepot = primaryActivity?.type === 'departure' || primaryActivity?.type === 'arrival' || primaryActivity?.type === 'depot'
        
        if (!graphNodes.has(nodeId)) {
          graphNodes.set(nodeId, {
            id: nodeId,
            name: pointLabel,
            symbol: shape,
            symbolSize: size * 1.5,
            itemStyle: { color: isDepot ? color : undefined },
            stopMeta
          })
        }
        
        if (prevNodeId !== null && prevNodeId !== nodeId) {
          graphLinks.push({
            source: prevNodeId,
            target: nodeId,
            lineStyle: { color, width: 2, curveness: 0.2 }
          })
        }
        prevNodeId = nodeId
      }
    })
  })

  if (isIndex) {
    series.push({
      type: 'graph',
      layout: 'force',
      force: {
        repulsion: 300,
        edgeLength: [50, 100],
        gravity: 0.1
      },
      roam: true,
      data: Array.from(graphNodes.values()),
      links: graphLinks,
      label: { show: true, position: 'right', formatter: '{b}' },
      tooltip: {
        formatter: (params: any) => {
          if (params.dataType === 'node') {
            const m = params.data?.stopMeta || {}
            return [
              `<b>${m.vehicleId || 'N/A'}</b> · ${m.pointLabel}`,
              `Type: ${m.actType}`,
              `Arrival: ${m.arrival}`,
              `Departure: ${m.departure}`,
              `Actual service: ${m.actualSvc}`,
              `Planned service: ${m.plannedSvc}`,
              `Time window: ${m.timeWindows}`,
              `Skills: ${m.skills}`,
              `Distance: ${m.distance}`,
              `Load: ${m.load}`,
            ].join('<br/>')
          } else if (params.dataType === 'edge') {
            return 'Route segment'
          }
        }
      }
    })
  }

  const baseOption: any = {
    title: { show: false },
    animationDuration: 300,
    animationDurationUpdate: 300,
    backgroundColor: 'transparent',
    tooltip: { trigger: 'item' },
    series
  }

  return baseOption
})

onMounted(() => {
  fetchProblems()
  
  if (mapContainer.value) {
    mainMapChart = echarts.init(mapContainer.value)
    mainMapChart.setOption(mapChartOption.value)
    const resizeObserver = new ResizeObserver(() => {
      mainMapChart?.resize()
    })
    resizeObserver.observe(mapContainer.value)
  }
})

watch(() => mapChartOption.value, (newOpt) => {
  if (mainMapChart && newOpt) {
    mainMapChart.setOption(newOpt, true)
  }
}, { deep: true })

watch(() => [isGeoMode.value, mapboxToken.value], async ([isGeo, token]) => {
  await nextTick()
  if (isGeo) {
    if (!mapboxMapInstance && token && mapboxContainer.value) {
      mapboxgl.accessToken = token as string
      mapboxMapInstance = new mapboxgl.Map({
        container: mapboxContainer.value,
        style: 'mapbox://styles/mapbox/dark-v11',
        center: [0, 0],
        zoom: 2
      })
      mapboxMapInstance.on('load', updateMapboxData)
    } else if (mapboxMapInstance) {
      mapboxMapInstance.resize()
      if (token) mapboxgl.accessToken = token as string
    }
  } else {
    if (mapContainer.value) {
      if (mainMapChart) mainMapChart.dispose()
      mainMapChart = echarts.init(mapContainer.value)
      mainMapChart.setOption(mapChartOption.value)
    }
  }
})

const updateMapboxData = () => {
  const map = mapboxMapInstance
  if (!map || !map.isStyleLoaded() || !currentSnapshot.value) return
  
  const step = currentSnapshot.value
  const lineFeatures: any[] = []
  const pointFeatures: any[] = []
  const unassignedFeatures: any[] = []
  
  let minLng = Infinity, maxLng = -Infinity, minLat = Infinity, maxLat = -Infinity
  let hasValidCoords = false
  
  const colors = [
    '#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#14b8a6', '#f97316'
  ]
  
  step.tours?.forEach((tour: any, index: number) => {
    const color = colors[index % colors.length]
    const coords: [number, number][] = []
    
    tour.stops?.forEach((stop: any) => {
      const act = stop.activities?.[0]
      const isGeo = stop.location?.lng !== undefined && stop.location?.lat !== undefined
      if (isGeo) {
        const lng = stop.location.lng
        const lat = stop.location.lat
        coords.push([lng, lat])
        hasValidCoords = true
        minLng = Math.min(minLng, lng)
        maxLng = Math.max(maxLng, lng)
        minLat = Math.min(minLat, lat)
        maxLat = Math.max(maxLat, lat)
        
        pointFeatures.push({
          type: 'Feature',
          geometry: { type: 'Point', coordinates: [lng, lat] },
          properties: {
            color: color,
            id: act?.jobId || 'depot',
            type: act?.type || 'stop',
            arrival: stop.time?.arrival || '',
            vehicleId: tour.vehicleId,
            radius: (act?.type === 'departure' || act?.type === 'arrival' || act?.type === 'depot') ? 8 : 5
          }
        })
      }
    })
    
    if (coords.length > 1) {
      lineFeatures.push({
        type: 'Feature',
        geometry: { type: 'LineString', coordinates: coords },
        properties: { color: color, vehicleId: tour.vehicleId }
      })
    }
  })
  
  step.unassigned?.forEach((item: any) => {
    if (item.location?.lng !== undefined) {
      const lng = item.location.lng
      const lat = item.location.lat
      hasValidCoords = true
      minLng = Math.min(minLng, lng)
      maxLng = Math.max(maxLng, lng)
      minLat = Math.min(minLat, lat)
      maxLat = Math.max(maxLat, lat)
      
      unassignedFeatures.push({
        type: 'Feature',
        geometry: { type: 'Point', coordinates: [lng, lat] },
        properties: {
            color: '#94a3b8',
            id: item.jobId || 'Unassigned',
            type: 'unassigned',
            radius: 5
        }
      })
    }
  })
  
  if (!map.getSource('vrp-lines')) {
    map.addSource('vrp-lines', { type: 'geojson', data: { type: 'FeatureCollection', features: lineFeatures } })
    map.addLayer({
      id: 'vrp-lines-layer',
      type: 'line',
      source: 'vrp-lines',
      layout: { 'line-join': 'round', 'line-cap': 'round' },
      paint: { 'line-color': ['get', 'color'], 'line-width': 2, 'line-opacity': 0.8 }
    })
    
    map.addSource('vrp-points', { type: 'geojson', data: { type: 'FeatureCollection', features: [...pointFeatures, ...unassignedFeatures] } })
    map.addLayer({
      id: 'vrp-points-layer',
      type: 'circle',
      source: 'vrp-points',
      paint: {
        'circle-radius': ['get', 'radius'],
        'circle-color': ['get', 'color'],
        'circle-stroke-width': 1,
        'circle-stroke-color': '#fff'
      }
    })
    
    const popup = new mapboxgl.Popup({ closeButton: false, closeOnClick: false })
    map.on('mouseenter', 'vrp-points-layer', (e: any) => {
        map.getCanvas().style.cursor = 'pointer'
        const p = e.features[0].properties
        const html = `<b>${p.vehicleId || 'N/A'}</b><br/>Type: ${p.type}<br/>ID: ${p.id}<br/>Arr: ${p.arrival || 'N/A'}`
        popup.setLngLat(e.features[0].geometry.coordinates).setHTML(html).addTo(map)
    })
    map.on('mouseleave', 'vrp-points-layer', () => {
        map.getCanvas().style.cursor = ''
        popup.remove()
    })
  } else {
    (map.getSource('vrp-lines') as mapboxgl.GeoJSONSource).setData({ type: 'FeatureCollection', features: lineFeatures });
    (map.getSource('vrp-points') as mapboxgl.GeoJSONSource).setData({ type: 'FeatureCollection', features: [...pointFeatures, ...unassignedFeatures] });
  }
  
  if (hasValidCoords && minLng !== Infinity && !currentProblemFitted) {
    currentProblemFitted = true
    if (minLng === maxLng) { minLng -= 0.05; maxLng += 0.05 }
    if (minLat === maxLat) { minLat -= 0.05; maxLat += 0.05 }
    map.fitBounds([[minLng, minLat], [maxLng, maxLat]], { padding: 60, duration: 1500 })
  }
}

watch(() => currentSnapshot.value, () => {
  if (isGeoMode.value) {
    updateMapboxData()
  }
}, { deep: true })


// Keep fetching updates
setInterval(() => {
  fetchProblems()
}, 2000)
</script>

<template>
  <a-config-provider :theme="{ algorithm: theme.darkAlgorithm }">
    <a-layout class="dashboard-shell">
    <a-layout-header class="dashboard-header">
      <div class="brand-block">
        <div class="brand-icon">
          <CarOutlined />
        </div>
        <div>
          <div class="brand-title">VRP Studio</div>
        </div>
      </div>

      <div class="toolbar">
        <a-upload
          action="/api/upload"
          :showUploadList="false"
          accept=".txt"
          @change="handleUploadChange"
          :disabled="running"
        >
          <a-button type="dashed" style="margin-right: 8px" :disabled="running">
            <template #icon><UploadOutlined /></template>
            Upload
          </a-button>
        </a-upload>
        <a-select
          v-model:value="selectedProblem"
          placeholder="Select a problem"
          style="min-width: 220px"
          :disabled="running || problems.length === 0"
          @change="fetchInitialState"
        >
          <a-select-option v-for="p in problems" :key="p.path" :value="p.path">
            <BookOutlined v-if="p.source === 'examples'" style="margin-right: 8px; color: #1890ff" />
            <UserOutlined v-else style="margin-right: 8px; color: #52c41a" />
            {{ p.name }}
          </a-select-option>
        </a-select>
        <a-input-number v-model:value="maxTime" :min="1" placeholder="Max Time (s)" style="width: 120px" :disabled="running" />
        <a-input-number v-model:value="maxGen" :min="1" placeholder="Max Gen" style="width: 120px" :disabled="running" />
        

        <a-button type="primary" v-if="!running" :icon="h(PlayCircleOutlined)" @click.prevent="startSolver" :disabled="!selectedProblem">Run</a-button>
        <a-button danger v-else :icon="h(StopOutlined)" @click="stopSolver">Stop</a-button>
      </div>
    </a-layout-header>

    <a-layout-content class="dashboard-content">
        <div v-if="runData.history.length === 0" class="empty-state">
          <a-empty description="Select a problem and click Run to start real-time solving" />
        </div>

        <a-row v-else :gutter="[16, 16]" align="stretch" class="dashboard-grid">
          <a-col :xs="24" :lg="16">
            <a-card class="main-card" :bordered="false">
              <template #title>
                <div class="card-title-row">
                  <div>
                    <div class="section-label">Current snapshot</div>
                    <div class="section-title">
                      Generation {{ currentStats?.generation }}
                      <span class="elapsed-inline" style="font-size: 13px; opacity: 0.8;" v-if="localElapsedSeconds > 0">
                        · {{ localElapsedSeconds.toFixed(1) }}s
                      </span>
                    </div>
                  </div>
                  <div class="summary-pill-group">
                    <a-tag color="green" v-if="currentStats?.is_new_best">New best</a-tag>
                    <a-tag class="solving-tag" v-else-if="running">
                      <div class="glow-circle"></div> Solving
                    </a-tag>
                    <a-tag color="green" v-else>Finished</a-tag>
                    <a-tag color="blue">Cost {{ currentStats?.cost?.toFixed(2) }}</a-tag>
                  </div>
                </div>
              </template>

              <div class="chart-shell" style="position: relative">
                  <div class="mapbox-token-floater" v-if="(!mapboxToken || !running) && isGeoMode">
                    <a-input-password
                      v-model:value="mapboxToken"
                      placeholder="Mapbox Token (Required for Mapbox)"
                      size="small"
                    />
                  </div>
                  <div v-show="!isGeoMode" ref="mapContainer" class="map-chart"></div>
                  <div v-show="isGeoMode" ref="mapboxContainer" class="map-chart"></div>
              </div>

              <template #extra>
                <div class="timeline-box">
                  <a-button :icon="h(StepBackwardOutlined)" @click="jumpToPreviousSolution">Previous</a-button>
                  <a-button type="primary" :icon="h(StepForwardOutlined)" @click="jumpToNextSolution">Next</a-button>
                </div>
              </template>
            </a-card>
          </a-col>

          <a-col :xs="24" :lg="8">
            <div class="right-column" style="display: flex; flex-direction: column; gap: 20px;">
              <a-row :gutter="[12, 12]">
                <!-- Row 1: Cost + Distance -->
                <a-col :xs="12">
                  <a-card class="metric-card" :bordered="false">
                    <a-statistic :value="currentStats?.cost?.toFixed(2) ?? 0" title="Cost" :prefix="h(DollarOutlined)" />
                  </a-card>
                </a-col>
                <a-col :xs="12">
                  <a-card class="metric-card" :bordered="false">
                    <a-statistic :value="currentStats?.distance ?? currentStats?.statistic?.distance ?? 0" title="Distance" :prefix="h(EnvironmentOutlined)" />
                  </a-card>
                </a-col>
                <!-- Row 2: Duration + Tours -->
                <a-col :xs="12">
                  <a-card class="metric-card" :bordered="false">
                    <a-statistic :value="currentStats?.duration ?? currentStats?.statistic?.duration ?? 0" title="Duration (s)" :prefix="h(FieldTimeOutlined)" />
                  </a-card>
                </a-col>
                <a-col :xs="12">
                  <a-card class="metric-card" :bordered="false">
                    <a-statistic :value="currentStats?.num_tours ?? currentStats?.tours?.length ?? 0" title="Tours" :prefix="h(CarOutlined)" />
                  </a-card>
                </a-col>
                <!-- Row 3: Driving + Serving -->
                <a-col :xs="12">
                  <a-card class="metric-card" :bordered="false">
                    <a-statistic :value="currentStats?.driving ?? currentStats?.statistic?.times?.driving ?? 0" title="Driving (s)" :prefix="h(DashboardOutlined)" />
                  </a-card>
                </a-col>
                <a-col :xs="12">
                  <a-card class="metric-card" :bordered="false">
                    <a-statistic :value="currentStats?.serving ?? currentStats?.statistic?.times?.serving ?? 0" title="Serving (s)" :prefix="h(InboxOutlined)" />
                  </a-card>
                </a-col>
                <!-- Row 4: Waiting + Break -->
                <a-col :xs="12">
                  <a-card class="metric-card" :bordered="false">
                    <a-statistic :value="currentStats?.waiting ?? currentStats?.statistic?.times?.waiting ?? 0" title="Waiting (s)" :prefix="h(HourglassOutlined)" />
                  </a-card>
                </a-col>
                <a-col :xs="12">
                  <a-card class="metric-card" :bordered="false">
                    <a-statistic :value="currentStats?.break ?? currentStats?.statistic?.times?.break ?? 0" title="Break (s)" :prefix="h(CoffeeOutlined)" />
                  </a-card>
                </a-col>
              </a-row>

              <a-card class="insight-card" :bordered="false">
                <template #title>
                  <div>
                    <div class="section-label">Convergence</div>
                    <div class="section-title">Best cost {{ latestBest?.cost?.toFixed(2) || 0 }}</div>
                  </div>
                </template>
                <div class="chart-shell compact-chart">
                  <v-chart
                    class="map-chart"
                    :key="`${selectedProblem}-convergence`"
                    :option="convergenceChartOption"
                    :update-options="{ notMerge: true }"
                    autoresize
                  />
                </div>
              </a-card>
            </div>
          </a-col>
        </a-row>
    </a-layout-content>
  </a-layout>
  </a-config-provider>
</template>

<style scoped>
.dashboard-shell {
  height: 100vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background:
    radial-gradient(circle at top left, rgba(99, 102, 241, 0.2), transparent 24%),
    radial-gradient(circle at bottom right, rgba(34, 211, 238, 0.14), transparent 18%),
    linear-gradient(135deg, #020617, #0f172a 46%, #111827);
}

.dashboard-header {
  height: auto;
  padding: 8px 16px;
  background: rgba(2, 6, 23, 0.72);
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.brand-block {
  display: flex;
  align-items: center;
  gap: 12px;
}

.brand-icon {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  display: grid;
  place-items: center;
  font-weight: 700;
  color: #fff;
  background: linear-gradient(135deg, #0ea5e9, #6366f1);
  box-shadow: 0 6px 16px rgba(14, 165, 233, 0.3);
  font-size: 14px;
}

.brand-title {
  font-size: 14px;
  font-weight: 700;
  color: #f8fafc;
}

.brand-subtitle {
  display: none;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.dashboard-content {
  flex: 1;
  padding: 16px;
  display: flex;
  flex-direction: column;
  min-height: 0; /* allows flex children to shrink */
}

/* Ensure the a-spin wrapper propagates the flex height down */
.dashboard-content :deep(.ant-spin-nested-loading),
.dashboard-content :deep(.ant-spin-container) {
  height: 100%;
  display: flex;
  flex-direction: column;
  flex: 1;
}

.dashboard-grid {
  flex: 1;
  height: 100%;
}

.dashboard-grid > .ant-col {
  height: 100%;
}

.right-column {
  width: 100%;
  height: 100%;
}

.empty-state {
  flex: 1;
  display: grid;
  place-items: center;
  border-radius: 20px;
  background: rgba(15, 23, 42, 0.58);
}

.main-card,
.metric-card,
.insight-card {
  background: rgba(8, 15, 30, 0.98) !important;
  border-radius: 22px !important;
  border: 1px solid rgba(148, 163, 184, 0.22) !important;
  box-shadow: 0 24px 60px rgba(15, 23, 42, 0.52);
  overflow: hidden;
}

.main-card {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.insight-card {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

/* Strip card body padding so the ECharts canvas can fill the full width */
.main-card :deep(.ant-card-body) {
  padding: 12px 16px;
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.insight-card :deep(.ant-card-body) {
  padding: 12px 16px;
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.metric-card {
  min-height: auto;
}

.metric-card :deep(.ant-card-body) {
  padding: 8px 12px;
}

:deep(.ant-statistic-title) {
  color: #e2e8f0 !important;
  font-size: 10px !important;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  margin-bottom: 2px !important;
}

:deep(.ant-statistic-content) {
  color: #f8fafc !important;
}

:deep(.ant-statistic-content-value) {
  font-size: 16px !important;
  font-weight: 700 !important;
}

.card-title-row,
.timeline-box {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.glow-circle {
  display: inline-block;
  width: 12px;
  height: 12px;
  border: 2px solid transparent;
  border-top-color: #38bdf8;
  border-right-color: #38bdf8;
  border-radius: 50%;
  animation: spin-glow 1s linear infinite;
  margin-right: 6px;
  vertical-align: middle;
}

@keyframes spin-glow {
  0% { transform: rotate(0deg); box-shadow: 0 0 2px #38bdf8; }
  50% { box-shadow: 0 0 8px #38bdf8, 0 0 12px #38bdf8; }
  100% { transform: rotate(360deg); box-shadow: 0 0 2px #38bdf8; }
}

.solving-tag {
  background: rgba(14, 165, 233, 0.1) !important;
  border: 1px solid rgba(14, 165, 233, 0.3) !important;
  color: #38bdf8 !important;
  display: inline-flex;
  align-items: center;
}

.summary-pill-group {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.section-label {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.2em;
  color: #94a3b8;
}

.section-title {
  font-size: 18px;
  font-weight: 700;
  color: #f8fafc;
}

.elapsed-inline {
  font-size: 13px;
  font-weight: 400;
  color: #94a3b8;
  margin-left: 6px;
}

.chart-shell {
  flex: 1;
  min-height: 0;
  border-radius: 18px;
  overflow: hidden;
  background: linear-gradient(180deg, rgba(15, 23, 42, 0.65), rgba(15, 23, 42, 0.25));
}

.compact-chart {
  /* let flex: 1 take over */
}

.map-chart {
  width: 100%;
  height: 100%;
}

.timeline-box {
  display: flex;
  align-items: center;
  gap: 12px;
}

.slider-row {
  margin-top: 18px;
}

.route-details-panel {
  margin-top: 18px;
  padding: 16px;
  border-radius: 18px;
  background: rgba(15, 23, 42, 0.55);
  border: 1px solid rgba(148, 163, 184, 0.16);
}

.route-details-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.route-details-content {
  display: grid;
  gap: 12px;
  max-height: 320px;
  overflow: auto;
  padding-right: 4px;
}

.stop-card {
  background: rgba(15, 23, 42, 0.78);
  border: 1px solid rgba(99, 102, 241, 0.2);
  border-radius: 16px;
  padding: 14px;
}

.stop-card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 10px;
}

.stop-card-title {
  font-size: 14px;
  font-weight: 700;
  color: #f8fafc;
}

.stop-card-subtitle {
  font-size: 12px;
  color: #94a3b8;
  margin-top: 4px;
}

.stop-meta-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px 14px;
}

.stop-meta-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.stop-meta-item.full-width {
  grid-column: 1 / -1;
}

.stop-meta-label {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #94a3b8;
}

.stop-meta-value {
  color: #f8fafc;
  font-size: 13px;
  word-break: break-word;
}

@media (max-width: 992px) {
  .dashboard-header {
    align-items: flex-start;
  }

  .toolbar {
    width: 100%;
  }

  .chart-shell {
    height: 480px;
  }
}

@media (max-width: 640px) {
  .stop-meta-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .dashboard-content {
    padding: 14px;
  }

  .brand-title {
    font-size: 16px;
  }

  .section-title {
    font-size: 16px;
  }
}
.mapbox-token-floater {
  position: absolute;
  top: 10px;
  left: 10px;
  z-index: 10;
  width: 160px;
  opacity: 0.8;
  transition: opacity 0.3s;
}

.mapbox-token-floater:hover {
  opacity: 1;
}

.mapbox-token-floater .ant-input-affix-wrapper {
  background: rgba(30, 41, 59, 0.8) !important;
  border: 1px solid rgba(255, 255, 255, 0.2) !important;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
}

.mapbox-token-floater .ant-input {
  background: transparent !important;
  color: #f8fafc;
}
</style>
