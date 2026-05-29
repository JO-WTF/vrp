# 1. Getting Started

## 1.1. Features

Python Interface 让 Rust VRP 求解器可以作为 Python 求解器程序使用，主要能力包括：

| 能力 | Python API | 说明 |
| --- | --- | --- |
| 建模 | `Problem` | 用 Python builder 或既有 JSON 定义 jobs、vehicles、relations、objectives。 |
| 路由数据 | `RoutingMatrix`, `MatrixCollection`, `get_locations` | 提取地点顺序，构造单 profile、多 profile 或 time-dependent matrix。 |
| 配置 | `Config`, `Objective`, `Recreate`, `Ruin`, `Population`, `Hyper` | 用 Python helper 组合 solver termination、population、ruin-recreate 和 hyper heuristic。 |
| 求解 | `solve` | 调用 native Rust solver，返回 `Solution`。 |
| 初始解 | `InitialSolution` | 将已有 route/tour 作为 warm start 输入。 |
| 校验 | `validate`, `check`, `CheckResult` | 求解前校验 problem/matrix，求解后检查 solution feasibility。 |
| 分析 | `Solution`, `TourView`, `StopView` | 读取 statistic、tours、stops、unassigned 和 GeoJSON。 |
| 迭代监听 | `on_iteration` | 在 Python 中接收中间解，用于日志、调参和可视化。 |
| 可视化记录 | `vrp_cli.vis.SolveTracker` | 记录优化历史并生成 dashboard/Studio 可消费的数据。 |
| 格式转换 | `convert_to_pragmatic` | 将外部科学/benchmark 格式转换为 pragmatic problem。 |

## 1.2. Installation

Python Interface 依赖一个带 PyO3 native extension 的 `vrp-cli` Python 包。安装时需要同时处理 Python 环境、Rust toolchain 和 maturin 构建。根据使用场景不同，推荐三种安装路径：

| 场景 | 推荐方式 | 说明 |
| --- | --- | --- |
| 只想在本仓库中运行示例和二次开发 | 使用仓库根目录 `build.sh` / `build.ps1` | 自动创建/复用 `.venv`、构建 Rust、构建 wheel 并安装。 |
| 正在开发 Python facade 或 native binding | 使用 `maturin develop` | 将 extension 直接安装到当前虚拟环境，适合快速迭代。 |
| 需要分发到其他 Python 项目 | 使用 `maturin build` 生成 wheel 后安装 | 适合 CI、发布或离线部署。 |

### 1.2.1. Prerequisites

安装前请确认以下依赖可用：

| 依赖 | 版本/要求 | 用途 | 检查命令 |
| --- | --- | --- | --- |
| Python | 3.10+ | 运行 Python facade 和构建 extension | `python --version` |
| Rust toolchain | stable | 编译 Rust solver 和 PyO3 extension | `rustc --version` / `cargo --version` |
| pip 或 uv | 任一可用 | 安装 Python 构建依赖和 wheel | `python -m pip --version` / `uv --version` |
| maturin | `vrp-cli/requirements.txt` 中声明 `maturin>=1.0` | 构建 PyO3 wheel | `maturin --version` |

如果尚未安装 Rust，可先安装 Rust stable toolchain。Linux/macOS 通常使用 rustup；Windows 建议使用 rustup 并准备好 C++ build tools。

### 1.2.2. Recommended repository installation

在仓库根目录使用项目提供的构建脚本是最稳妥的方式。该脚本会：

1. 创建或复用仓库根目录 `.venv`。
2. 构建 Rust workspace。
3. 安装 `vrp-cli/requirements.txt` 中的 Python 构建依赖。
4. 在 `vrp-cli` 包中调用 maturin 构建 wheel。
5. 将最新 wheel 安装回 `.venv`。
6. 运行 `import vrp_cli` 做安装验证。

Linux/macOS：

```bash
# 推荐：如果已安装 uv，脚本会自动创建 .venv
./build.sh

# 清理后重新构建
./build.sh --clean

# 只构建/安装 Python binding，跳过 Rust workspace 预构建
./build.sh --no-rust

# 调试构建
./build.sh --debug
```

Windows PowerShell：

```powershell
# 推荐：如果已安装 uv，脚本会自动创建 .venv
.\build.ps1

# 清理后重新构建
.\build.ps1 -Clean

# 只构建/安装 Python binding，跳过 Rust workspace 预构建
.\build.ps1 -NoRust

# 调试构建
.\build.ps1 -Debug
```

如果没有安装 `uv`，请先手动创建 `.venv`：

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
./build.sh
```

Windows：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
.\build.ps1
```

### 1.2.3. Manual development installation with maturin

如果你正在修改 `vrp-cli/python/vrp_cli` 或 `vrp-cli/src/lib.rs`，推荐使用 `maturin develop`，它会把当前源码构建并安装到已激活的虚拟环境中。

Linux/macOS：

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r vrp-cli/requirements.txt
cd vrp-cli
maturin develop --features py_bindings
cd ..
```

Windows PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r vrp-cli\requirements.txt
cd vrp-cli
maturin develop --features py_bindings
cd ..
```

也可以使用 `uv`：

```bash
uv venv .venv
uv pip install --python .venv/bin/python -r vrp-cli/requirements.txt
cd vrp-cli
uv run --python ../.venv/bin/python maturin develop --features py_bindings
cd ..
```

> 注意：`maturin develop` 应在包含 `vrp-cli/pyproject.toml` 的目录中执行，或显式指定 manifest。仓库根目录的 `pyproject.toml` 是 uv workspace 配置，不是 PyO3 包构建配置。

### 1.2.4. Wheel build and installation

如果需要把 Python Interface 安装到其他 Python 项目或部署环境，可以先构建 wheel：

```bash
cd vrp-cli
maturin build --release --features py_bindings
cd ..
```

构建产物默认位于仓库根目录的 `target/wheels/`。安装最新 wheel：

```bash
python -m pip install --force-reinstall target/wheels/vrp_cli-*.whl
```

Windows PowerShell：

```powershell
python -m pip install --force-reinstall (Get-ChildItem target\wheels\vrp_cli-*.whl | Sort-Object LastWriteTime -Descending | Select-Object -First 1).FullName
```

### 1.2.5. Verification

安装完成后，先验证 Python package 和 native extension 都可导入：

```bash
python - <<'PY'
import vrp_cli
from vrp_cli import Problem, RoutingMatrix, Config, solve
print("vrp_cli imported from:", vrp_cli.__file__)
print("public API sample:", Problem, RoutingMatrix, Config, solve)
PY
```

再运行一个仓库示例：

```bash
python examples/python-interop/run_pragmatic_example.py --list
python examples/python-interop/run_pragmatic_example.py simple.basic.problem.json
```

如果你使用 `.venv` 但没有激活环境，可以直接使用虚拟环境 Python：

```bash
.venv/bin/python examples/python-interop/run_pragmatic_example.py simple.basic.problem.json
```

Windows：

```powershell
.\.venv\Scripts\python.exe examples\python-interop\run_pragmatic_example.py simple.basic.problem.json
```

### 1.2.6. Development checks

二次开发时建议至少执行：

```bash
cargo check --features py_bindings
python -m unittest discover -s vrp-cli/python/tests
python examples/python-interop/basic.py
```

这些命令分别验证：

- Rust/PyO3 binding 可以编译。
- Python facade 测试通过。
- 安装后的 package 可以真实运行一个求解示例。

### 1.2.7. Troubleshooting

| 问题 | 常见原因 | 处理方式 |
| --- | --- | --- |
| `cargo: command not found` | 未安装 Rust 或 PATH 未生效 | 安装 Rust stable toolchain，并重新打开 shell。 |
| `maturin: command not found` | 当前环境未安装 maturin | 执行 `python -m pip install -r vrp-cli/requirements.txt`。 |
| `No module named vrp_cli` | wheel 未安装到当前 Python 环境 | 确认已激活 `.venv`，或使用 `.venv/bin/python` / `.venv\Scripts\python.exe`。 |
| `No module named vrp_cli._vrp_cli` | Python 源码可见但 native extension 未构建/安装 | 重新执行 `maturin develop --features py_bindings` 或 `./build.sh`。 |
| `pip not found in .venv` | Python 环境缺少 ensurepip/pip | 使用 `uv venv .venv`，或安装系统的 python venv/ensurepip 支持后重建 `.venv`。 |
| Windows 编译失败 | 缺少 MSVC/C++ build tools | 安装 Visual Studio Build Tools 的 C++ workload 后重试。 |

## 1.3. Defining problem

### 1.3.1. Builder style

最直接的方式是从 `Problem.empty()` 开始，用 builder 添加任务和车辆：

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
    .add_pickup(
        "pickup_1",
        (52.52250, 13.40950),
        [1],
        duration=240,
        times=[["2019-07-04T10:00:00Z", "2019-07-04T16:00:00Z"]],
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
```

Builder 方法会修改当前 problem 并返回 `self`，因此适合链式调用。常用字段提供命名参数；尚未封装的 pragmatic 字段可以通过 raw dict 或 `**extra` 透传。

### 1.3.2. JSON asset style

如果已有原始 pragmatic JSON 文件，可以直接加载：

```python
from pathlib import Path
from vrp_cli import Problem

problem = Problem.from_json(Path("examples/data/pragmatic/simple.basic.problem.json"))
```

也可以从 dict 构造：

```python
problem = Problem.from_dict({
    "plan": {"jobs": []},
    "fleet": {"vehicles": [], "profiles": []},
})
```

### 1.3.3. Python-side validation

在求解前可以先执行：

```python
problem.validate_problem()
```

该校验用于发现明显问题，例如没有车辆、没有任务、capacity/demand 维度不一致。更完整的 schema 和业务约束校验由 native validator 完成：

```python
from vrp_cli import validate

validate(problem)
```

## 1.4. Acquiring routing info

Rust solver 需要 routing matrix 描述任意两个 location 之间的 travel time 和 distance。推荐流程如下：

1. 从 problem 中提取有序去重 locations。
2. 用这些 locations 调用外部 routing engine 或业务系统。
3. 按相同顺序构造 `RoutingMatrix`。
4. 将矩阵传给 `solve`。

```python
locations = problem.get_locations()

# 假设外部 routing 服务按 locations 顺序返回 2x2 矩阵
matrix = RoutingMatrix(
    profile="normal_car",
    durations=[0, 609, 609, 0],
    distances=[0, 3840, 3840, 0],
)
```

二维矩阵可以使用 `from_2d`：

```python
matrix = RoutingMatrix.from_2d(
    durations=[[0, 1800], [1800, 0]],
    distances=[[0, 5000], [5000, 0]],
    profile="normal_car",
)
```

> 注意：Python API 使用 `durations` 作为输入名，序列化到 pragmatic JSON 时会转换为 `travelTimes`。

## 1.5. Running solver

### 1.5.1. Minimal solve

```python
from vrp_cli import Config, solve

config = Config(max_time=5, max_generations=1000)
solution = solve(problem, matrices=[matrix], config=config)
```

### 1.5.2. With iteration callback

```python
def on_iteration(generation, solution):
    print(generation, solution.total_cost, len(solution.tours))

solution = solve(
    problem,
    matrices=[matrix],
    config=Config(max_time=10, max_generations=5000),
    on_iteration=on_iteration,
    every=100,
)
```

### 1.5.3. With initial solution

```python
from vrp_cli import InitialSolution

initial = InitialSolution.from_json("initial.solution.json")
solution = solve(problem, matrices=[matrix], config=config, initial_solution=initial)
```

### 1.5.4. With heuristic helpers

```python
from vrp_cli import Config, Recreate

config = (
    Config(max_time=30, max_generations=5000)
    .set_initial(
        Recreate.cheapest(),
        alternatives=[Recreate.farthest(), Recreate.regret(2, 3)],
    )
    .set_population_rosomaxa(selection_size=8)
)
```

## 1.6. Analyzing results

`solve` 返回 `Solution`：

```python
print(solution.total_cost)
print(solution.statistic)
print(solution.unassigned)
```

遍历 tours 和 stops：

```python
for tour in solution.iter_tours():
    print(tour.vehicle_id, tour.distance, tour.duration)
    for stop in tour.iter_stops():
        print(stop.location, stop.arrival, stop.departure, stop.job_ids())
```

检查可行性：

```python
from vrp_cli import check

result = check(problem, solution, matrices=[matrix])
if not result:
    print(result.violations)
    result.raise_if_infeasible()
```

导出结果：

```python
solution.write_json("solution.json", indent=2)
geojson = solution.geojson
```

## 1.7. Evaluating performance

### 1.7.1. Solver termination

最常见的性能参数是：

- `max_time`：最大运行时间，单位秒。
- `max_generations`：最大 generation 数。
- variation termination：当解质量变化足够小的时候提前停止。
- `parallelism`：并行计算配置。

示例：

```python
config = Config(max_time=60, max_generations=10000).set_parallelism((2, 4))
```

### 1.7.2. Iteration tracking

使用 callback 或 tracker 记录成本变化：

```python
from vrp_cli.vis.tracker import SolveTracker

tracker = SolveTracker(run_name="experiment_001", problem=problem)
solution = solve(problem, matrices=[matrix], config=config, on_iteration=tracker.callback, every=50)
tracker.finish()
```

### 1.7.3. What to measure

建议记录：

- final cost、distance、duration。
- unassigned job 数量和原因。
- elapsed seconds。
- generation。
- new best 出现频率。
- 不同 config/preset 下的结果稳定性。
