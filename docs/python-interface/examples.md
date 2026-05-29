# 3. Examples

## 3.1. Pragmatic format

Python Interface 的示例位于 `examples/python-interop`，覆盖从最小求解到复杂配置、结果分析和可视化记录的常见场景。

### 3.1.1. Basic feature usage

| 示例 | 用途 | 建议阅读场景 |
| --- | --- | --- |
| `basic.py` | 用 Python builder 定义 delivery、pickup、vehicle、matrix、config 并求解。 | 第一次使用 Python Interface。 |
| `json_assets.py` | 从仓库已有 pragmatic JSON 加载 problem/matrix/config。 | 已经有 JSON 输入，希望在 Python 中求解。 |
| `location_index.py` | 处理 location index 和 routing locations。 | 需要对接外部 routing engine。 |
| `multi_profile.py` | 使用多个 profile/matrix。 | 多车型、多交通方式或不同 routing profile。 |
| `time_dependent.py` | 使用 timestamp matrix。 | 路况随时间变化的业务。 |

### 3.1.1.1. Basic job usage

```bash
python examples/python-interop/basic.py
```

该示例展示：

- `Problem.empty()`。
- `add_delivery` 和 `add_pickup`。
- `add_vehicle`。
- `RoutingMatrix`。
- `Config` 和 `Recreate`。
- `solve`。

### 3.1.1.2. JSON asset usage

```bash
python examples/python-interop/json_assets.py
```

该示例适合从 CLI/原 Rust 文档迁移到 Python 的用户。它不重建 problem，而是直接加载：

- `Problem.from_json(...)`
- `RoutingMatrix.from_json(...)`
- `Config.from_json(...)`

### 3.1.1.3. Relations

```bash
python examples/python-interop/relations.py
```

该示例展示如何在 Python 中表达 job 与 vehicle 的约束关系。适合需要锁车、固定顺序或保留已有调度计划的业务。

### 3.1.1.4. Break, reload and resources

```bash
python examples/python-interop/break_reload.py
```

该示例展示与 vehicle shift resources 相关的配置。适合多趟运输、司机休息、补货或站点资源场景。

### 3.1.1.5. Objectives

```bash
python examples/python-interop/objectives.py
```

该示例展示 `Objective` helper 的组合方式。适合希望从默认 cost 优化扩展到 load balancing、distance balancing 或 value maximization 的业务。

## 3.1.2. Solver configuration examples

| 示例 | 用途 |
| --- | --- |
| `config_export.py` | 构造并导出 config JSON。 |
| `config_types.py` | 展示 typed config helper。 |
| `hyper_config.py` | 展示 hyper heuristic、ruin-recreate、local search 组合。 |
| `initial_solution.py` | 展示 initial solution/warm start。 |
| `callback.py` | 展示 iteration callback。 |

### Callback example

```python
def on_iteration(generation, solution):
    print(generation, solution.total_cost)

solution = solve(problem, matrices=[matrix], config=config, on_iteration=on_iteration, every=100)
```

### Initial solution example

初始解适合：

- 使用历史调度结果 warm start。
- 在新订单加入后保留部分路线结构。
- 做人工计划与 solver 结果的比较。

## 3.1.3. Solution analysis examples

| 示例 | 用途 |
| --- | --- |
| `solution_inspect.py` | 展示 `Solution`、`TourView`、`StopView` 的 rich accessor。 |
| `visualization_dataset.py` | 生成用于可视化的数据。 |
| `visualization.py` | 记录求解过程并服务给前端查看。 |

### Solution inspection

```python
for tour in solution.iter_tours():
    print(tour.vehicle_id, tour.cost, tour.distance)
    for stop in tour.iter_stops():
        print(stop.arrival, stop.departure, stop.job_ids())
```

## 3.2. Python project integration

### 3.2.1. Use as a library

在业务项目中，建议把 Python Interface 包装成应用服务的一个模块：

```python
class VrpSolverService:
    def __init__(self, config):
        self.config = config

    def solve_plan(self, orders, vehicles, matrix):
        problem = build_problem_from_domain(orders, vehicles)
        solution = solve(problem, matrices=[matrix], config=self.config)
        check(problem, solution, matrices=[matrix]).raise_if_infeasible()
        return solution
```

### 3.2.2. Input/output boundary

推荐边界：

- 业务系统 → Python Interface：domain objects 转 `Problem` 和 `RoutingMatrix`。
- Python Interface → Rust solver：JSON string，通过 native binding。
- Rust solver → Python Interface：solution JSON。
- Python Interface → 业务系统：`Solution` accessor 或转换后的 domain route model。

### 3.2.3. Error handling pattern

```python
try:
    validate(problem, matrices=[matrix])
    solution = solve(problem, matrices=[matrix], config=config)
    check(problem, solution, matrices=[matrix]).raise_if_infeasible()
except ValueError as err:
    # Python facade validation or checker error
    raise
except OSError as err:
    # Native parser/solver/checker error exposed by PyO3 binding
    raise
```

## 3.3. Visualization and Studio

### 3.3.1. Offline tracker

```python
from vrp_cli.vis.tracker import SolveTracker

tracker = SolveTracker(run_name="demo", problem=problem)
solution = solve(problem, matrices=[matrix], config=config, on_iteration=tracker.callback, every=50)
tracker.finish()
```

输出文件可用于离线 dashboard 或实验复盘。

### 3.3.2. VRP Studio

VRP Studio 是基于 Python Interface 的实时可视化应用。它通过 FastAPI 后端调用 `Problem`、`RoutingMatrix`、`Config` 和 `solve(on_iteration=...)`，通过 WebSocket 把中间解推给前端。

详见：[`../vrp-studio.md`](../vrp-studio.md)。
