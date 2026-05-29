# 3. Internals

## 3.1. Overview

Python Interface 的内部架构分为四层：

```text
Python application / examples / VRP Studio
        │
        ▼
Python facade (`vrp_cli`)
        │ JSON strings and callbacks
        ▼
PyO3 native module (`vrp_cli._vrp_cli`)
        │ Rust API calls
        ▼
Rust VRP solver / checker / converter
```

### 3.1.1. Python facade

主要职责：

- 提供 Python public API。
- 将 Python dict/list/path/string 归一化为 asset。
- 生成 pragmatic JSON。
- 做轻量前置校验。
- 包装 native 返回的 JSON 为 `Solution` 或其他 asset。
- 将 native callback 中的 solution JSON 包装为 Python `Solution`。

详细模块文档：

- [Assets & Builders](internals/assets-builders.md)
- [Visualization Tracker](internals/visualization.md)

### 3.1.2. Native binding

PyO3 binding 暴露 Rust 能力：

| Python facade 调用 | Native function | Rust 能力 |
| --- | --- | --- |
| `solve` | `solve_pragmatic` | 求解 pragmatic problem。 |
| `solve(..., initial_solution=...)` | `solve_pragmatic_with_init` | 使用初始解求解。 |
| `solve(..., on_iteration=...)` | `solve_pragmatic_with_callback` | 求解并回传中间解。 |
| `validate` | `validate_pragmatic` | problem/matrix 校验。 |
| `check` | `check_pragmatic_solution` | solution 可行性检查。 |
| `convert_to_pragmatic` | `convert_to_pragmatic` | 外部格式转换。 |
| `get_locations` | `get_routing_locations` | 提取 routing locations。 |

### 3.1.3. Data contract

所有跨 Python/Rust 边界的数据都应满足：

- JSON-compatible。
- schema 与 pragmatic format 对齐。
- 错误信息可追踪到 problem/config/matrix/solution。
- callback 传递的是 snapshot，不应在回调中修改 solver 内部状态。

## 3.2. Development

### 3.2.1. Project structure

| 路径 | 说明 |
| --- | --- |
| `vrp-cli/python/vrp_cli/__init__.py` | Python facade 主实现。 |
| `vrp-cli/python/vrp_cli/vis/` | 可视化 tracker 和本地 server。 |
| `vrp-cli/src/lib.rs` | FFI、WASM、PyO3 binding 入口。 |
| `vrp-cli/python/tests/` | Python facade 和 native binding 测试。 |
| `examples/python-interop/` | Python 使用示例。 |
| `docs/src/examples/interop/python/` | Python Interface 使用和二次开发文档。 |

### 3.2.2. Solver extension

新增能力时先判断扩展点：

| 需求 | 推荐扩展点 |
| --- | --- |
| 新增 Python 便捷建模方法 | `Problem` builder。 |
| 新增 matrix 构造方式 | `RoutingMatrix` classmethod 或 `MatrixCollection`。 |
| 新增 heuristic 配置 helper | `Config` 或 typed helper。 |
| 新增 Rust solver 已有能力的 Python 调用 | PyO3 binding + Python facade wrapper。 |
| 新增结果字段访问 | `Solution`、`TourView` 或 `StopView`。 |
| 新增可视化指标 | `SolveTracker` 和 VRP Studio snapshot。 |

更细流程见：[Development Guide](internals/development.md)。

### 3.2.3. Development practices

- Python helper 不应改变 solver 语义，只负责生成 solver 已理解 of JSON。
- 如果 schema 可变或高级，保留 raw dict 入口。
- Public API 新增后必须有测试和示例。
- 对 callback、initial solution、matrix list 等路径要覆盖组合场景。
- 文档中的代码片段应能直接复制或说明前置条件。

### 3.2.4. Testing

常用测试：

```bash
cargo check --features py_bindings
python -m unittest discover -s vrp-cli/python/tests
python examples/python-interop/basic.py
```

如果只改文档，至少检查：

- Markdown 文件存在并能被链接。
- 标题层级符合文档结构。
- 示例命令和 API 名称与代码一致。

## 3.3. Algorithms

Python Interface 不重新实现算法。核心算法仍由 Rust solver 提供，包括：

- construction heuristic。
- ruin-recreate。
- local search。
- population-based search。
- rosomaxa。
- termination 和 telemetry。

Python 层可以做的是：

- 用 `Config` 暴露算法参数。
- 用 `Objective` 和 helper 组织优化目标。
- 用 callback 观察算法过程。
- 用 tracker 和 Studio 对算法行为做可视化分析。

如果需要修改算法本身，应进入 Rust core；如果只是让 Python 用户更容易配置算法，则在 Python Interface 中新增 helper。
