<script setup lang="ts">
import { computed, onMounted, ref, h, watch } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, ScatterChart, LinesChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, TitleComponent, LegendComponent, DataZoomComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import { PlayCircleOutlined, StopOutlined, DollarOutlined, EnvironmentOutlined, FieldTimeOutlined, CarOutlined, DashboardOutlined, InboxOutlined, HourglassOutlined, CoffeeOutlined, StepBackwardOutlined, StepForwardOutlined } from '@ant-design/icons-vue'
import { theme, message } from 'ant-design-vue'
use([CanvasRenderer, LineChart, ScatterChart, LinesChart, GridComponent, TooltipComponent, TitleComponent, LegendComponent, DataZoomComponent])

const problems = ref<any[]>([])
const selectedProblem = ref<string | null>(null)
const maxTime = ref<number>(60)
const maxGen = ref<number>(3000)

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

const fetchInitialState = async (path: string) => {
  try {
    const res = await fetch('/api/problem/initial_state', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ problem_path: path })
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
  if (newVal && !running.value) {
    fetchInitialState(newVal)
  }
})

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

// Per-job metadata (time windows, service duration, demand) from the JSON
const jobsMeta = computed<Record<string, any>>(() => runData.value?.jobs_meta ?? {})

// Helper: format seconds as "Xh Ym Zs" or "Xm Zs"
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

  currentStep.tours.forEach((tour: any) => {
    const color = getVehicleColor(tour.vehicleId)
    const coords: [number, number][] = []
    const scatterData: any[] = []

    tour.stops.forEach((stop: any, stopIndex: number) => {
      if (stop.location?.lng !== undefined && stop.location?.lat !== undefined) {
        const x = stop.location.lng
        const y = stop.location.lat
        const activities = stop.activities || []
        const primaryActivity = activities[0]
        const jobId: string = primaryActivity?.jobId ?? ''
        const pointLabel = jobId || primaryActivity?.type || `Stop ${stopIndex + 1}`

        const fmtLoad = (load: unknown): string => {
          if (Array.isArray(load)) return load.length ? load.join(', ') : 'N/A'
          return load === undefined || load === null ? 'N/A' : String(load)
        }

        // Actual service duration from solution timestamps
        const actualSvcSecs = (() => {
          const arr = Date.parse(stop.time?.arrival)
          const dep = Date.parse(stop.time?.departure)
          if (!stop?.time?.arrival || !stop?.time?.departure || isNaN(arr) || isNaN(dep)) return null
          return Math.round((dep - arr) / 1000)
        })()

        // Job metadata from problem definition (may be absent for older runs)
        const jm = jobsMeta.value[jobId]
        const place0 = jm?.places?.[0]
        const plannedSvcSecs: number | undefined = place0?.duration
        const timeWindows: any[][] | undefined = place0?.times
        const twStr = timeWindows?.length
          ? timeWindows.map((tw: any[]) => `${tw[0]} – ${tw[1]}`).join(', ')
          : undefined

        const isDepot = primaryActivity?.type === 'departure' || primaryActivity?.type === 'arrival' || primaryActivity?.type === 'depot'
        
        coords.push([x, y])
        hasValidCoords = true
        scatterData.push({
          name: pointLabel,
          value: [x, y],
          symbol: isDepot ? 'rect' : 'circle',
          symbolSize: isDepot ? 12 : 8,
          stopMeta: {
            jobId,
            pointLabel,
            actType: primaryActivity?.type || 'stop',
            vehicleId: tour.vehicleId,
            lat: y,
            lng: x,
            arrival: stop.time?.arrival || 'N/A',
            departure: stop.time?.departure || 'N/A',
            actualSvc: actualSvcSecs !== null ? fmtSecs(actualSvcSecs) : 'N/A',
            plannedSvc: plannedSvcSecs !== undefined ? fmtSecs(plannedSvcSecs) : '—',
            timeWindows: twStr ?? '—',
            distance: stop.distance ?? 'N/A',
            load: fmtLoad(stop.load),
          }
        })
      }
    })

    const lineTooltip = {
      formatter: () => {
        return [
          `<b>${tour.vehicleId}</b>`,
          `Distance: ${tour.statistic?.distance ?? 'N/A'}`,
          `Duration: ${tour.statistic?.duration != null ? fmtSecs(tour.statistic.duration) : 'N/A'}`
        ].join('<br/>')
      }
    }

    if (coords.length > 1) {
      // First segment: Depot to the first demand point (solid line)
      series.push({
        type: 'lines',
        coordinateSystem: 'cartesian2d',
        data: [{ coords: [coords[0], coords[1]] }],
        lineStyle: { color, width: 2.2, opacity: 0.9, type: 'solid' },
        zlevel: 1,
        tooltip: lineTooltip
      })
    }

    if (coords.length > 2) {
      // Subsequent segments: Connect the rest with dashed lines
      series.push({
        type: 'lines',
        coordinateSystem: 'cartesian2d',
        polyline: true,
        data: [{ coords: coords.slice(1) }],
        lineStyle: { color, width: 2.2, opacity: 0.6, type: 'dashed' },
        zlevel: 1,
        tooltip: lineTooltip
      })
    }

    if (scatterData.length > 0) {
      series.push({
        type: 'scatter',
        coordinateSystem: 'cartesian2d',
        data: scatterData,
        // symbolSize and symbol are defined in the data items
        itemStyle: { color },
        zlevel: 2,
        tooltip: {
          formatter: (params: any) => {
            const m = params.data?.stopMeta || {}
            const lines = [
              `<b>${m.vehicleId}</b> · ${m.pointLabel}`,
              `Type: ${m.actType}`,
              `Lat/Lng: ${fmtCoord(m.lat)}, ${fmtCoord(m.lng)}`,
              `Arrival: ${m.arrival}`,
              `Departure: ${m.departure}`,
              `Actual service: ${m.actualSvc}`,
              `Planned service: ${m.plannedSvc}`,
              `Time window: ${m.timeWindows}`,
              `Distance: ${m.distance}`,
              `Load: ${m.load}`,
            ]
            return lines.join('<br/>')
          }
        }
      })
    }
  })

  if (currentStep.unassigned?.length) {
    const unassignedData = currentStep.unassigned
      .filter((item: any) => item.location?.lng !== undefined)
      .map((item: any) => ({
        name: item.jobId || 'Unassigned',
        value: [item.location.lng, item.location.lat]
      }))

    if (unassignedData.length > 0) {
      series.push({
        type: 'scatter',
        coordinateSystem: 'cartesian2d',
        data: unassignedData,
        symbolSize: 6,
        itemStyle: { color: '#94a3b8' },
        zlevel: 2,
        tooltip: { formatter: (params: any) => `Unassigned: ${params.name}` }
      })
    }
  }

  if (!hasValidCoords) {
    return {
      backgroundColor: 'transparent',
      title: {
        text: 'No valid coordinates found',
        left: 'center',
        top: 'center',
        textStyle: { color: '#cbd5e1', fontSize: 16 }
      }
    }
  }

  return {
    title: { show: false },
    animationDuration: 300,
    animationDurationUpdate: 300,
    backgroundColor: 'transparent',
    tooltip: { trigger: 'item' },
    grid: { left: 16, right: 16, top: 16, bottom: 16, containLabel: false },
    xAxis: {
      type: 'value',
      scale: true,
      axisLine: { show: false },
      axisLabel: { show: false },
      splitLine: { show: false }
    },
    yAxis: {
      type: 'value',
      scale: true,
      axisLine: { show: false },
      axisLabel: { show: false },
      splitLine: { show: false }
    },
    dataZoom: [
      { type: 'inside', xAxisIndex: 0, filterMode: 'none' },
      { type: 'inside', yAxisIndex: 0, filterMode: 'none' }
    ],
    series
  }
})

onMounted(() => {
  fetchProblems()
})
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
        <a-select
          v-model:value="selectedProblem"
          :options="problems.map((p) => ({ label: p.name, value: p.path }))"
          placeholder="Select a problem"
          style="min-width: 220px"
          :disabled="running || problems.length === 0"
        />
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

              <div class="chart-shell">
                  <v-chart
                    class="map-chart"
                    :key="`${selectedProblem}`"
                    :option="mapChartOption"
                    :update-options="{ notMerge: true }"
                  autoresize
                />
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
</style>
