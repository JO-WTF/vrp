# Python Interface Solver Documentation

## Introduction

`vrp-cli` Python Interface 是在原作者 Rust VRP 求解器基础上进行二次开发得到的 Python 求解器界面。它的定位不是简单的命令行封装，而是一个可以在 Python 项目、Notebook、服务端程序和可视化系统中直接使用的求解器程序：用户可以用 Python 对象定义 VRP 问题、准备 routing matrix、配置启发式求解参数、运行 Rust 求解器、检查可行性、分析结果并记录优化过程。

底层仍复用原 Rust 项目的 pragmatic format、solver、checker、converter 和序列化能力；上层则提供 Python 风格的 facade：`Problem`、`RoutingMatrix`、`Config`、`InitialSolution`、`Solution`、`solve`、`check`、`validate` 和可视化 tracker。

本文档结构参考原作者 VRP 文档组织方式（https://reinterpretcat.github.io/vrp/concepts/pragmatic/problem/index.html），按“Getting Started → Concepts → Examples → Internals”的顺序说明 Python Interface 作为独立求解器程序的使用方式和二次开发方式。

## Documentation map

* [1. Getting Started](python-interface/getting-started.md)
  * [1.1. Features](python-interface/getting-started.md#11-features)
  * [1.2. Installation](python-interface/getting-started.md#12-installation)
  * [1.3. Defining problem](python-interface/getting-started.md#13-defining-problem)
  * [1.4. Acquiring routing info](python-interface/getting-started.md#14-acquiring-routing-info)
  * [1.5. Running solver](python-interface/getting-started.md#15-running-solver)
  * [1.6. Analyzing results](python-interface/getting-started.md#16-analyzing-results)
  * [1.7. Evaluating performance](python-interface/getting-started.md#17-evaluating-performance)
* [2. Concepts](python-interface/concepts.md)
  * [2.1. Pragmatic format in Python](python-interface/concepts.md#21-pragmatic-format-in-python)
    * [2.1.1. Modeling a problem](python-interface/concepts.md#211-modeling-a-problem)
    * [2.1.1.1. Jobs](python-interface/concepts.md#2111-jobs)
    * [2.1.1.2. Vehicles](python-interface/concepts.md#2112-vehicles)
    * [2.1.1.3. Resources](python-interface/concepts.md#2113-resources)
    * [2.1.1.4. Relations](python-interface/concepts.md#2114-relations)
    * [2.1.1.5. Clustering](python-interface/concepts.md#2115-clustering)
    * [2.1.1.6. Objectives](python-interface/concepts.md#2116-objectives)
    * [2.1.2. Routing data](python-interface/concepts.md#212-routing-data)
    * [2.1.3. Solution model](python-interface/concepts.md#213-solution-model)
    * [2.1.4. Error index and validation](python-interface/concepts.md#214-error-index-and-validation)
  * [2.2. Scientific formats](python-interface/concepts.md#22-scientific-formats)
* [3. Examples](python-interface/examples.md)
  * [3.1. Pragmatic format](python-interface/examples.md#31-pragmatic-format)
  * [3.2. Python project integration](python-interface/examples.md#32-python-project-integration)
  * [3.3. Visualization and Studio](python-interface/examples.md#33-visualization-and-studio)
* [4. Internals](python-interface/internals.md)
  * [4.1. Overview](python-interface/internals.md#41-overview)
  * [4.2. Development](python-interface/internals.md#42-development)
  * [4.3. Algorithms](python-interface/internals.md#43-algorithms)

## Solver interface at a glance

```python
from vrp_cli import Config, Problem, Recreate, RoutingMatrix, solve

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
    )
)

matrix = RoutingMatrix(
    profile="normal_car",
    durations=[0, 609, 609, 0],
    distances=[0, 3840, 3840, 0],
)

config = Config(max_time=5, max_generations=1000).set_initial(
    Recreate.cheapest(),
    alternatives=[Recreate.farthest(), Recreate.regret(2, 3)],
)

solution = solve(problem, matrices=[matrix], config=config)
print(solution.statistic)
```

## Relationship with the original Rust project

Python Interface 继承原 Rust 项目的核心概念：pragmatic problem、routing matrix、solution model、constraints、objectives、checker 和 heuristic solver。差异在于：

| 原 Rust/CLI 工作流 | Python Interface 工作流 |
| --- | --- |
| 编写 JSON 文件后用 CLI 求解。 | 在 Python 中用 builder 或 JSON asset 构造问题并直接调用 `solve`。 |
| routing matrix 以 pragmatic JSON 字段传递。 | Python 中可使用 `RoutingMatrix(durations=..., distances=...)`，序列化时自动转换为 `travelTimes`。 |
| 输出 JSON 需要用户自行解析。 | `Solution` 提供 `statistic`、`tours`、`unassigned`、`geojson`、`iter_tours()` 等访问入口。 |
| 中间迭代状态主要面向内部 solver。 | `on_iteration` 回调和 `SolveTracker` 可以在 Python 中记录、展示和分析优化过程。 |
| 二次开发主要在 Rust crate 内完成。 | Python facade 可继续扩展 builder、config helper、可视化数据和上层应用集成。 |

## Recommended reading path

1. 第一次使用：阅读 [Getting Started](python-interface/getting-started.md)，复制最小示例跑通求解。
2. 需要建模复杂业务：阅读 [Concepts](python-interface/concepts.md)，理解 jobs、vehicles、resources、relations、objectives、routing data 和 solution model。
3. 需要找可运行样例：阅读 [Examples](python-interface/examples.md)，选择与业务最接近的脚本。
4. 需要扩展接口：阅读 [Internals](python-interface/internals.md) 和更细的开发文档。
