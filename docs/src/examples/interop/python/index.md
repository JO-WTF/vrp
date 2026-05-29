# Python Interface Solver Documentation

## Introduction

`vrp-cli` Python Interface 是在 [Rust VRP 求解器](https://reinterpretcat.github.io/vrp) 基础上进行二次开发封装 of Python 求解器接口。它的定位是将原有的 Rust 求解能力暴露给 Python 开发者，从而实现纯 Python 环境下的建模、求解、分析和可视化闭环。

Python Interface 使 Rust VRP 求解器可以被无缝集成到 Python 生态中，其主要能力包括：

| 能力 | Python API | 说明 |
| --- | --- | --- |
| 建模 | `Problem` | 提供 Python builder 模式或直接通过 JSON 加载，支持定义 jobs、vehicles、relations 和 objectives。 |
| 路由数据 | `RoutingMatrix`, `MatrixCollection`, `get_locations` | 提供地点顺序提取，支持构造单 profile、多 profile 甚至 time-dependent matrix。 |
| 配置 | `Config`, `Objective`, `Recreate`, `Ruin`, `Population`, `Hyper` | 提供 Python helper 用于灵活组合 solver termination、population、ruin-recreate 以及 hyper heuristic。 |
| 求解 | `solve` | 直接调用底层 native Rust solver，返回类型化的 `Solution` 对象。 |
| 初始解 | `InitialSolution` | 支持将已有的 route/tour 作为 warm start 输入以加速收敛。 |
| 校验 | `validate`, `check`, `CheckResult` | 求解前校验 problem 与 matrix；求解后检查 solution feasibility，确保结果合法。 |
| 分析 | `Solution`, `TourView`, `StopView` | 方便读取 statistic、tours、stops、unassigned 列表以及 GeoJSON 格式的数据。 |
| 迭代监听 | `on_iteration` | 在 Python 环境中实时接收中间解，便于开发日志、调参及可视化监控。 |
| 可视化记录 | `vrp_cli.vis.SolveTracker` | 记录优化历史过程，并生成供 dashboard/Studio 消费的展示数据。 |
| 格式转换 | `convert_to_pragmatic` | 支持将外部科研/benchmark 格式一键转换为 pragmatic problem。 |

在底层，Python Interface 充分复用了原 Rust 项目强大的 pragmatic format、solver、checker 及序列化能力；在上层，它则通过更符合 Python 习惯的 facade 接口对外暴露：`Problem`、`RoutingMatrix`、`Config`、`InitialSolution`、`Solution`、`solve`、`check`、`validate` 和可视化 tracker。

## Documentation Map

* [1. Getting Started](getting-started.md)
  * [1.1. Prerequisites](getting-started.md#11-prerequisites)
  * [1.2. Installation](getting-started.md#12-installation)
  * [1.3. Defining problem](getting-started.md#13-defining-problem)
  * [1.4. Building routing matrix](getting-started.md#14-building-routing-matrix)
  * [1.5. Running solver](getting-started.md#15-running-solver)
  * [1.6. Analyzing results](getting-started.md#16-analyzing-results)
  * [1.7. Complete example](getting-started.md#17-complete-example)
* [2. Concepts](concepts.md)
  * [2.1. Pragmatic format in Python](concepts.md#21-pragmatic-format-in-python)
    * [2.1.1. Modeling a problem](concepts.md#211-modeling-a-problem)
      * [2.1.1.1. Jobs](concepts.md#2111-jobs)
      * [2.1.1.2. Vehicles](concepts.md#2112-vehicles)
      * [2.1.1.3. Resources](concepts.md#2113-resources)
      * [2.1.1.4. Relations](concepts.md#2114-relations)
      * [2.1.1.5. Clustering](concepts.md#2115-clustering)
      * [2.1.1.6. Objectives](concepts.md#2116-objectives)
    * [2.1.2. Routing data](concepts.md#212-routing-data)
    * [2.1.3. Solution model](concepts.md#213-solution-model)
    * [2.1.4. Error index and validation](concepts.md#214-error-index-and-validation)
  * [2.2. Scientific formats](concepts.md#22-scientific-formats)
* [3. Internals](internals.md)
  * [3.1. Overview](internals.md#31-overview)
    * [Assets & Builders](internals/assets-builders.md)
    * [Visualization Tracker](internals/visualization.md)
  * [3.2. Development](internals.md#32-development)
    * [Development Guide](internals/development.md)
    * [3.2.1. Project structure](internals.md#321-project-structure)
    * [3.2.2. Solver extension](internals.md#322-solver-extension)
    * [3.2.3. Development practices](internals.md#323-development-practices)
    * [3.2.4. Testing](internals.md#324-testing)
  * [3.3. Algorithms](internals.md#33-algorithms)
* [4. VRP Studio](vrp-studio.md)

## Solver Interface at a Glance

```python
from vrp_cli import Config, Problem, Recreate, RoutingMatrix, solve

# 1. 建模 (Modeling)
problem = (
    Problem.empty()
    .add_delivery(
        "delivery_1",
        (52.52599, 13.45413),
        [1],
        duration=300,
        times=[["2019-07-04T09:00:00Z", "2019-07-04T18:00:00Z"]],
    )
    .add_vehicle(
        "vehicle_1",
        start_location=(52.5316, 13.3884),
        start_earliest="2019-07-04T09:00:00Z",
        end_location=(52.5316, 13.3884),
        end_latest="2019-07-04T18:00:00Z",
        capacity=[10],
        costs={"fixed": 22, "distance": 0.0002, "time": 0.005},
        profile="normal_car",
    )
)

# 2. 路由数据 (Routing Data)
matrix = RoutingMatrix(
    profile="normal_car",
    durations=[0, 609, 609, 0],
    distances=[0, 3840, 3840, 0],
)

# 3. 求解配置 (Solver Configuration)
config = Config(max_time=5, max_generations=1000).set_initial(
    Recreate.cheapest(),
    alternatives=[Recreate.farthest(), Recreate.regret(2, 3)],
)

# 4. 执行求解 (Execution)
solution = solve(problem, matrices=[matrix], config=config)

# 5. 分析结果 (Analysis)
print(solution.statistic)
```

## Recommended Reading Path

1. **第一次使用**：阅读 [Getting Started](getting-started.md)，复制并运行最小示例以跑通求解流程。
2. **需要建模复杂业务**：阅读 [Concepts](concepts.md)，深入理解 jobs、vehicles、resources、relations、objectives、routing data 及 solution model 等核心概念。
3. **需要寻找可运行的样例代码**：参考 [examples/python-interop/README.md](../../../../../examples/python-interop/README.md) 并运行 `examples/python-interop/` 目录下的示例脚本。
4. **需要扩展底层或阅读源码**：阅读 [Internals](internals.md) 及其相关的架构设计与开发文档。
