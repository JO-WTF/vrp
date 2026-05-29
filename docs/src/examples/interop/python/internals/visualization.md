# 可视化 Tracker 模块

## 文档信息

| 项目 | 内容 |
| --- | --- |
| 文档类型 | 模块设计与二次开发说明 |
| 适用模块 | `vrp_cli.vis.tracker`, `vrp_cli.vis.server`, Python callback visualization flow |
| 主要源码 | `vrp-cli/python/vrp_cli/vis/tracker.py`, `vrp-cli/python/vrp_cli/vis/server.py` |
| 目标读者 | 需要记录 solver 轨迹、接入 dashboard 或扩展 VRP Studio 数据的开发者 |

---

## 1. 设计目标

`vrp_cli.vis` 的目标是把 `solve(on_iteration=...)` 产生的中间解转换为稳定的历史数据，供前端可视化、实验复盘或调试分析使用。它不参与求解，只消费 problem metadata 和 solution snapshot。

---

## 2. SolveTracker 职责

`SolveTracker` 负责：
- 提供可直接传给 `solve` 的 `callback(generation, solution)`。
- 仅在发现新 best solution 时记录 snapshot，降低历史数据体积。
- 在 `finish()` 中补写最终 snapshot，保证可视化有结束状态。
- 将 history 写入 `.vrp_vis_data/<run_name>.json`。
- 将 problem 中的 job metadata 写入顶层 `jobs_meta`。

典型用法：

```python
tracker = SolveTracker(run_name="demo", problem=problem)
solution = solve(problem, matrices=[matrix], config=config, on_iteration=tracker.callback, every=10)
tracker.finish()
```

---

## 3. History JSON 契约

输出 JSON 顶层结构：

```json
{
  "run_name": "demo",
  "start_time": 0,
  "end_time": 0,
  "jobs_meta": {},
  "history": []
}
```

单条 history 记录包含：

| 字段 | 说明 |
| --- | --- |
| `generation` | solver generation/state。 |
| `elapsed_seconds` | 从 tracker 创建到该 snapshot 的耗时。 |
| `cost` | 当前 solution total cost。 |
| `is_new_best` | 是否为新 best solution。 |
| `distance` / `duration` | solution statistic 摘要。 |
| `driving` / `serving` / `waiting` / `break` | time statistic 摘要。 |
| `statistic` | 原始 statistic dict，保留向后兼容。 |
| `num_tours` | tours 数量。 |
| `num_unassigned` | unassigned 数量。 |
| `tours` | 当前 solution tours。 |
| `unassigned` | 当前未分配任务。 |

新增字段时应保持旧字段不删除，并允许前端在字段缺失时降级。

---

## 4. Job Metadata 契约

`_extract_jobs_meta(problem)` 从 problem 提取 job 相关信息，常见字段包括：
- job type：pickup、delivery、service、replacement。
- places：location、duration、time windows。
- demand。
- skills。
- priority。
- value。
- placesByType。

这些 metadata 用于 tooltip、unassigned 展示、Gantt 和 Data Inspector。扩展 metadata 时应注意：
- 不要改变已有字段含义。
- 新字段优先作为可选字段加入。
- 对多 place、多 task type 的 job 保留类型分组。
- 需要考虑未分配任务只有 job id、没有完整 activity 的情况。

---

## 5. Flush 与文件写入

Tracker 使用临时文件再替换目标文件的方式写入，降低写到一半被前端读取的风险。扩展时应保持：
- JSON 始终可解析。
- 文件路径由 `save_dir` 和 `run_name` 控制。
- 大量 snapshot 场景下避免每代无条件 flush。

---

## 6. 静态可视化服务

`vrp_cli.vis.server` 提供轻量静态文件服务，用于打开可视化前端。它适合本地调试和快速演示；生产级实时可视化由 VRP Studio 的 FastAPI/WebSocket 流程承担。

二次开发时，如果只是调整 tracker 输出，不一定需要修改 server；如果改变前端资源路径或 dist 结构，才需要同步调整。

---

## 7. 与 VRP Studio 的关系

`SolveTracker` 是离线/轻量记录工具；VRP Studio 则是实时 WebSocket 工具。两者共享的设计思想是：
- 通过 callback 获取中间 solution。
- 将 solution 压缩为 snapshot。
- 提取 problem metadata 帮助前端解释 job。
- 保持 history 数据结构稳定。

如果要新增前端展示字段，应优先定义通用 snapshot 字段，再分别接入 tracker 和 Studio 后端，避免两套可视化输出分裂。

---

## 8. 测试建议

| 测试类型 | 断言内容 |
| --- | --- |
| metadata 提取 | 不同 job type、time windows、demand、skills 正确提取。 |
| callback 记录 | cost 改善时新增 snapshot，未改善时不新增。 |
| finish 行为 | 最终 snapshot 被写入。 |
| JSON 写入 | history 文件可解析，顶层字段完整。 |
| 向后兼容 | 旧前端依赖字段不被删除或改名。 |

---

## 9. 扩展示例

新增一个 `lateness` 指标的推荐路径：
1. 确认 `Solution.statistic` 或 stops 中已有 lateness 来源。
2. 在 `_record` 中读取并写入 `lateness` 字段。
3. 保留原始 `statistic`。
4. 添加 tracker 单测，验证字段存在且缺失时为 `None` 或 0。
5. 更新 VRP Studio 前端或离线前端展示。
