# VRP Studio 工作说明

## 1. 工作定位

VRP Studio 是本阶段新增的实时可视化与调试工具，目标是把 VRP 求解过程从“运行命令后查看最终 JSON”提升为“浏览器中观察问题、配置求解、实时接收迭代解、分析指标、检查路线和未分配任务”的交互式体验。

它依赖 Python interface 提供的对象封装、solver callback 和 solution 访问能力，并在此基础上提供 FastAPI 后端、WebSocket 实时通道和 Vue 前端 dashboard。

## 2. 总体架构

```text
浏览器前端（Vue + Vite + ECharts + Mapbox GL）
        │
        │ REST: problem list / upload / initial state
        │ WebSocket: solve stream
        ▼
FastAPI 后端（vrp_studio.server）
        │
        │ 调用 Python interface
        ▼
vrp_cli Python facade
        │
        │ PyO3 native binding
        ▼
Rust VRP solver / checker / parser
```

主要目录：

| 路径 | 作用 |
| --- | --- |
| `vrp-studio/vrp_studio/server.py` | FastAPI 后端、问题扫描、上传转换、初始状态接口、WebSocket 求解流。 |
| `vrp-studio/vrp_studio/solomon.py` | Solomon 文本格式解析与 pragmatic problem/matrix 转换。 |
| `vrp-studio/frontend/src/App.vue` | Studio 主界面，包含问题选择、参数面板、地图、指标、Gantt、数据检查和播放控制。 |
| `vrp-studio/frontend/src/config.ts` | 前端运行时后端地址配置。 |
| `vrp-studio/frontend/public/config.js` | 部署后可直接修改的浏览器端配置文件。 |
| `vrp-studio/deploy.sh` / `deploy.ps1` | 一键安装后端依赖、构建前端、复制静态资源并启动服务。 |
| `vrp-studio/README.md` | 启动、部署和后端地址配置说明。 |

## 3. 后端功能

### 3.1 问题扫描接口

`GET /api/problems` 会在若干默认目录中查找 `*.problem.json`：

- `data`
- `examples/data`
- `../data`
- `../examples/data`

如果旁边存在同名 `*.matrix.json`，接口会同时返回 matrix path。返回数据包含 problem id、展示名称、problem path、matrix path 和来源标记。

### 3.2 上传与 Solomon 转换

`POST /api/upload` 支持上传 Solomon 格式文件。后端读取文本后调用 `parse_solomon`，生成：

- pragmatic problem JSON
- routing matrix JSON

转换后的文件保存到 `data` 或 `../data`，文件名基于问题名称生成，并尽量避免用户手动准备 pragmatic JSON 的成本。

### 3.3 初始状态接口

`POST /api/problem/initial_state` 用于在求解前给前端提供初始可视化状态，包含：

- `jobs_meta`：任务类型、地点、时间窗、duration、demand、skills、priority、value 等元数据。
- `initial_state.tours`：车辆起点、break 点、recharge 站、reload 点等静态点位。
- `initial_state.unassigned`：尚未求解前所有 job/activity 的位置，便于地图先展示问题分布。

这个接口使前端不必等 solver 返回第一轮结果，也能立即渲染 depot、job 和资源点。

### 3.4 WebSocket 求解流

`/ws/solve` 是 VRP Studio 的核心实时接口。前端发送求解请求后，后端会启动 `SolverThread` 执行 solver，并把以下消息推给前端：

- `metadata`：任务元数据。
- `iteration`：新的 best solution snapshot。
- `done`：最终结果或正常结束。
- `error`：异常信息。
- `stopped`：用户停止后的状态。

`SolverThread` 内部会：

1. 通过 `Problem.from_json` 加载 problem。
2. 如有 matrix path，则通过 `RoutingMatrix.from_json` 加载矩阵。
3. 根据前端选择的 heuristic mode 生成 preset config。
4. 叠加 max time、max generations、variation、parallelism 等用户参数。
5. 调用 `vrp_cli.solve(..., on_iteration=..., every=10)`。
6. 仅在 cost 改善时把 snapshot 推入队列，减少前端刷新压力。
7. 求解结束后发送 final snapshot。

### 3.5 Heuristic preset 与运行参数

前端可以配置：

- `maxTime`
- `maxGen`
- `parallelism`
- variation termination 参数
- `heuristicMode`

后端目前支持以下 heuristic preset：

| 模式 | 说明 |
| --- | --- |
| `default` | 使用默认 solver config，再叠加用户 termination。 |
| `fast` | 使用较小 elitism population，适合快速反馈。 |
| `deep` | 使用 rosomaxa population，并提高探索比例。 |
| `large_scale` | 面向较大规模问题的 rosomaxa/static-selective 配置。 |

## 4. 前端功能

### 4.1 问题选择与运行控制

前端主界面提供：

- 自动加载 problem list。
- 上传 Solomon 文件并转换。
- 选择 problem 后加载 initial state。
- 配置求解参数。
- 启动、停止 solver。
- 通过 WebSocket 接收实时结果。

### 4.2 地图可视化

VRP Studio 目前支持两套地图路径：

- **Mapbox GL JS**：当用户提供 Mapbox token 且问题为地理坐标模式时启用，提供真实地图底图和交互点位。
- **ECharts geo fallback**：没有 Mapbox token 时自动回退，避免本地调试或无 token 环境无法使用。

地图展示内容包括：

- 车辆路线 polyline。
- depot、pickup、delivery、service、replacement、break、recharge、reload 等不同 activity type 的点位。
- 未分配任务点。
- hover tooltip 中展示 job id、activity type、坐标、time windows、demand、duration、skills、priority、value、unassigned reason 等信息。

本阶段对地图体验做了多次改进：

- 从 ECharts/Leaflet 迁移到 Mapbox GL JS。
- 增加无 token 时的 ECharts fallback。
- 修复地图容器初始化时机问题。
- 修复 ECharts job marker 填充和 symbol artifact。
- 按 activity type 统一颜色、图标和 symbol。
- 增强 time window tooltip 对比度，并统一使用 UTC 日期格式。
- 支持显示 unassigned jobs，并在面板中显示 unassigned metric。

### 4.3 指标 Dashboard

前端基于 solver snapshot 展示指标卡与图表，包括：

- 总成本 cost。
- distance。
- duration。
- driving / serving / waiting / break 等 time statistic。
- route/tour 数量。
- unassigned 数量。
- elapsed seconds。
- generation。

Convergence chart 可以随历史 snapshot 展示 cost 和其他指标的变化，便于观察 solver 是否仍在改进。

### 4.4 Gantt Chart

Gantt 视图将每辆车的 stops 和 activities 按时间轴展开，帮助分析：

- 到达时间和离开时间。
- 服务时间、等待时间、行驶时间。
- break、reload、recharge 等特殊活动。
- 各车辆任务分布是否均衡。

配合 UTC 时间格式和高对比 tooltip，可以更直观地排查时间窗、等待和行程安排问题。

### 4.5 Data Inspector

Data Inspector 面向调试场景，提供当前 snapshot 的结构化数据查看能力，包括：

- 当前 tours。
- stops 与 activities。
- unassigned 列表。
- job metadata。
- statistic 原始字段。

它适合在地图和图表显示异常时进一步定位数据来源。

### 4.6 历史回放 Slider

Studio 保存前端收到的 history，并提供 playback slider：

- 可以在不同 generation 的 snapshot 之间切换。
- 可以播放/暂停优化过程。
- 地图、Gantt、指标和 data inspector 会随当前 history index 同步变化。

这使用户不仅能看到最终解，还能复盘 solver 如何逐步改善路线。

## 5. 部署与配置

### 5.1 一键部署脚本

仓库根目录执行：

```bash
./vrp-studio/deploy.sh
```

Windows：

```powershell
.\vrp-studio\deploy.ps1
```

脚本主要做以下事情：

1. 创建或复用根目录 `.venv`。
2. 安装 `vrp-studio/requirements.txt` 后端依赖。
3. 安装 `vrp-studio` 后端包。
4. 在 `vrp-studio/frontend` 中安装 npm 依赖并执行 build。
5. 把 `frontend/dist` 复制到 `vrp_studio/frontend/dist`，由 FastAPI 托管。
6. 默认启动服务。

常用参数包括：

```bash
./vrp-studio/deploy.sh --clean --port 8000
./vrp-studio/deploy.sh --no-start
```

### 5.2 手动启动

推荐使用 `uv`：

```bash
uv venv .venv
uv pip install --python .venv/bin/python -r vrp-studio/requirements.txt
uv run --python .venv/bin/python vrp-studio --port 8000
```

如果本地尚未安装可用的 `vrp-cli` Python binding，需要先完成上层构建或安装。

### 5.3 后端地址与 CORS

前端启动时会加载 `/config.js`。默认配置适合同一个 FastAPI 服务同时托管前端和 API 的场景。如果前端和后端分离部署，可以修改部署产物中的 `config.js`：

```js
window.VRP_STUDIO_CONFIG = {
  API_BASE_URL: "https://vrp-api.example.com:8000",
  WS_BASE_URL: "wss://vrp-api.example.com:8000",
}
```

或者使用拆分字段：

```js
window.VRP_STUDIO_CONFIG = {
  BACKEND_PROTOCOL: "https",
  BACKEND_HOST: "vrp-api.example.com",
  BACKEND_PORT: "8000",
}
```

如果前后端不同源，可通过环境变量限制允许访问的前端域名：

```bash
VRP_STUDIO_CORS_ORIGINS=https://studio.example.com uv run --python .venv/bin/python vrp-studio --port 8000
```

## 6. 当前成果总结

VRP Studio 已经形成了“数据发现/上传转换 → 参数配置 → WebSocket 实时求解 → 地图展示 → 指标分析 → Gantt 时间轴 → 数据检查 → 历史回放”的完整闭环。它把 Python interface 的 solver callback 能力产品化为浏览器应用，显著提升了 VRP 问题调试、演示和算法迭代分析的效率。
