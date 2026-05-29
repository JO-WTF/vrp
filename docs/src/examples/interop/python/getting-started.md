# 1. Getting Started

## 1.1. Prerequisites

安装前请确保已就绪以下环境：

- **Python 3.10+** (运行与构建: `python --version`)
- **Rust stable toolchain** (编译环境: `cargo --version`，Windows 需另备 C++ build tools)
- **pip** 或 **uv** (依赖管理: `pip --version` / `uv --version`)
- **maturin >= 1.0** (构建 PyO3: `maturin --version`)

## 1.2. Installation

VRP 求解器的核心计算模块由 Rust 编写以保证极致性能，并通过 Python 接口供上层调用。根据你的使用场景，有两种安装方式：

### 1.2.1. 标准构建与安装

如果你希望在 Python 项目中直接使用本项目进行车辆路径问题建模和求解，可以运行根目录下的脚本进行标准安装。

- **Linux/macOS**: `./build.sh`
- **Windows**: `.\build.ps1`

构建脚本会自动创建虚拟环境 (`.venv`)、编译 Rust 工程并安装生成的 `.whl` 包。构建完成后，生成的分发包默认存放于仓库根目录的 `target/wheels/` 目录下。

### 1.2.2. 开发环境与增量编译

如果你希望修改 Python 或 Rust 源码进行二次开发或调试，建议通过 `maturin develop` 命令来进行底层增量编译，并将最新的动态链接库安装至开发环境 the virtual environment，而不需要重新执行完整的打包脚本。

```bash
pip install -r vrp-cli/requirements.txt
cd vrp-cli
maturin develop --release --features py_bindings
```
*(注：`--release` 用于开启性能优化以测试真实的求解速度。若仅修改外层 Python 代码且希望获得最快的增量编译速度，可将其省略)*

### 1.2.3. 验证安装

安装完成后，运行一个仓库示例验证是否可用：

```bash
uv run examples/python-interop/run_pragmatic_example.py simple.basic.problem.json
```
注：若提示 `No module named vrp_cli`，请检查是否已激活 `.venv`，或确认使用的为虚拟环境内的 Python 解释器。

## 1.3. Defining problem

求解器的 Python interface 支持两种方式来定义问题：使用 `Problem` 类的 builder 模式，或者直接加载 Pragmatic 格式的 JSON 文件。

### 1.3.1. Builder style

如果你希望在代码中动态构建问题，可以从 `Problem.empty()` 开始，使用链式调用逐个添加配送任务 (delivery/pickup) 与车辆资源 (vehicle)：

```python
from vrp_cli import Problem

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
```

### 1.3.2. JSON asset style

本项目的标准业务描述规范被称为 **Pragmatic Format**。如果你已经有一份按照该格式编写的 JSON 配置文件，可以直接加载：

```python
from pathlib import Path
from vrp_cli import Problem

problem = Problem.from_json(Path("examples/data/pragmatic/simple.basic.problem.json"))
```

支持通过 Python 字典构造：

```python
problem = Problem.from_dict({
    "plan": {"jobs": []},
    "fleet": {"vehicles": [], "profiles": []},
})
```

### 1.3.3. Python-side validation

求解前可执行基础校验：

```python
problem.validate_problem()
```

此操作用于识别基础问题（如缺少车辆、任务缺失、容量维度不匹配）。完整的 schema 及业务约束校验由原生验证器提供：

```python
from vrp_cli import validate

validate(problem)
```

## 1.4. Building routing matrix

求解器依赖 routing matrix 获取地点间的耗时与距离数据。标准处理流程如下：

1. 从 problem 实例提取去重后的位置序列 (locations)。
2. 将位置序列传递给外部路径规划服务 (routing engine)。
3. 根据返回结果构造 `RoutingMatrix`。
4. 将矩阵实例传入 `solve` 方法。

```python
locations = problem.get_locations()

# 示例：假设问题中有两个位置 A 和 B，其矩阵形式为：   
# 耗时 (durations)                             距离 (distances)
#               A               B                      A               B
# A  [          0,            609 ]        A  [        0,           3840 ]
# B  [        609,              0 ]        B  [     3840,              0 ]

# 默认情况下，RoutingMatrix 期望接收按行展平（flatten）后的一维数组：
matrix = RoutingMatrix(
    profile="normal_car",
    durations=[0, 609, 609, 0], # 即 [A->A, A->B, B->A, B->B]
    distances=[0, 3840, 3840, 0], # 即 [A->A, A->B, B->A, B->B]
)
```

如果你的外部服务直接返回二维列表（即以嵌套列表形式表示的 N×N 矩阵），则无需在 Python 中手动将其展平为一维数组，直接使用 `from_2d` 方法构造即可：

```python
matrix = RoutingMatrix.from_2d(
    durations=[[0, 609], [609, 0]], # 即 [[A->A, A->B], [B->A, B->B]]
    distances=[[0, 3840], [3840, 0]], # 即 [[A->A, A->B], [B->A, B->B]]
    profile="normal_car",
)
```

> 注意：Python API 使用 `durations` 作为输入名，序列化到 pragmatic JSON 时会转换为 `travelTimes`。

## 1.5. Running solver

最简单的求解过程只需配置最大运行时间和迭代次数：

```python
from vrp_cli import Config, solve

# 配置基础终止条件
config = Config(max_time=5, max_generations=1000)

# 执行求解
solution = solve(problem, matrices=[matrix], config=config)
```

## 1.6. Analyzing results

求解完成后，`solve` 函数会返回一个 `Solution` 对象。你可以读取关键指标、遍历路线、检查约束或直接导出结果。

获取核心统计指标：

```python
print(f"总成本: {solution.total_cost}")
print(f"统计详情: {solution.statistic}")
print(f"未分配任务: {solution.unassigned}")
```

遍历路线 (Tours) 与停靠点 (Stops)：

```python
for tour in solution.iter_tours():
    print(f"车辆: {tour.vehicle_id}, 距离: {tour.distance}, 耗时: {tour.duration}")
    for stop in tour.iter_stops():
        print(f"位置: {stop.location}, 到达: {stop.arrival}, 离开: {stop.departure}, 任务: {stop.job_ids()}")
```

检查解的可行性（确保结果符合所有硬约束）：

```python
from vrp_cli import check

result = check(problem, solution, matrices=[matrix])
if not result:
    print(f"约束冲突: {result.violations}")
    result.raise_if_infeasible()
```

导出最终结果与可视化数据：

```python
# 导出为标准的 Pragmatic JSON 文件
solution.write_json("solution.json", indent=2)

# 提取 GeoJSON 供前端地图直接渲染
geojson_data = solution.geojson
```

## 1.7. Complete example

以下是将上述所有步骤整合在一起的完整可运行代码：

```python
from vrp_cli import Problem, RoutingMatrix, Config, solve, check

# 1. 构建问题 (Modeling)
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

# 2. 基础校验 (Validation)
problem.validate_problem()

# 3. 注入路由矩阵数据 (Routing Data)
locations = problem.get_locations()
matrix = RoutingMatrix(
    profile="normal_car",
    durations=[0, 609, 609, 0],
    distances=[0, 3840, 3840, 0],
)

# 4. 执行求解 (Solving)
config = Config(max_time=5, max_generations=1000)
solution = solve(problem, matrices=[matrix], config=config)

# 5. 输出解与验证 (Analyzing & Feasibility Check)
print(f"总成本: {solution.total_cost}")
print(f"统计详情: {solution.statistic}")
print(f"未分配任务: {solution.unassigned}\n")

for tour in solution.iter_tours():
    print(f"车辆: {tour.vehicle_id}, 距离: {tour.distance}, 耗时: {tour.duration}")
    for stop in tour.iter_stops():
        print(f"位置: {stop.location}, 到达: {stop.arrival}, 离开: {stop.departure}, 任务: {stop.job_ids()}")

result = check(problem, solution, matrices=[matrix])
if not result:
    print(f"约束冲突: {result.violations}")
    result.raise_if_infeasible()

# 6. 导出文件 (Export)
solution.write_json("solution.json", indent=2)
print("\n结果已成功导出至 solution.json")
```
