# Python API Assets, Config & Solve Bindings

## 文档信息

| 项目 | 内容 |
| --- | --- |
| 文档类型 | 模块设计与二次开发说明 |
| 适用模块 | `JsonAsset`, `Problem`, `RoutingMatrix`, `MatrixCollection`, `InitialSolution`, `Config`, `Objective`, `Hyper`, `solve`, `validate`, `check`, `Solution`, `TourView`, `StopView`, PyO3 Binding |
| 主要源码 | `vrp-cli/python/vrp_cli/__init__.py`, `vrp-cli/src/lib.rs` |
| 目标读者 | 需要新增/修改 Python Interface public API、Helper、求解配置或底层 binding 的开发者 |

---

## 1. 数据资产与 Builder 模块

数据资产层的核心目标是让 Python 用户用对象和 builder 完成 pragmatic JSON 的构造，同时保证所有对象最终仍可无损序列化为 Rust solver 接收的 JSON。该层不应重新定义 VRP 求解语义，只负责输入数据的组织、轻量校验和用户体验。

### 1.1. 通用资产契约：`JsonAsset`

`JsonAsset` 是 problem、matrix、config、solution 等对象的基础抽象，提供统一的 JSON 读写能力：
- `from_json(source)`：从路径、JSON 字符串或 JSON-like 输入构造。
- `from_dict(data)`：从 Python dict/list 构造。
- `to_dict()`：返回深拷贝，保护内部状态。
- `to_json(**kwargs)`：序列化为 JSON 字符串。
- `write_json(path, **kwargs)`：写入磁盘。

**扩展规则**：
1. 新增资产类时建议继承 `JsonAsset`（除非对象不是 JSON 资产）。
2. 在构造函数中将 dataclass、pydantic model、path-like 等输入转换为 JSON-compatible dict/list。
3. 对外返回深拷贝，避免用户绕过 builder 修改 `_data`。

### 1.2. Problem 模块与 Builder 设计

`Problem` 表示 pragmatic problem definition，负责：
- 创建空 problem skeleton。
- 添加 delivery、pickup、pickup-delivery、service 等 job 结构。
- 添加 vehicle、profile、shift、capacity、cost、time window 等字段。
- 管理 relation、objective 等 pragmatic 扩展结构。

**Builder 设计约定**：
* **链式返回**：修改当前 problem 后返回 `self`，便于 `Problem.empty().add_vehicle(...).add_delivery(...)`。
* **显式常用字段**：对常用字段提供命名参数，例如 `location`, `demand`, `duration`, `times`, `capacity`。
* **透传扩展字段**：对尚未建模的 pragmatic 字段允许 `**extra` 或 raw dict。
* **统一 location 形态**：复用 `_location`，允许 index、coordinate dict 或已成型 location dict。

### 1.3. RoutingMatrix 与 MatrixCollection

* **`RoutingLocations`**：表示 native 提取出的有序去重地点列表。二次开发者不应在 Python 层自行推导 location 顺序，因为 Rust solver 和 matrix index 对顺序敏感。
* **`RoutingMatrix`**：对 pragmatic matrix 做 Python 友好封装。一维/二维矩阵入参使用 `durations` 表示时间矩阵，序列化时转换为 pragmatic 字段 `travelTimes`。
* **`MatrixCollection`**：用于将多个 `RoutingMatrix` 组合后传给 solver。序列化时转换为矩阵列表。

### 1.4. InitialSolution

`InitialSolution` 表示传入 solver 的初始路线，用于 warm start 或固定部分路线。它支持从 raw JSON 加载，也支持从 `Solution` 或 tour-like Python 数据结构构造。

---

## 2. Config 与 Heuristic Helper 模块

配置模块的目标是把 solver config JSON 转换成 Python 可组合的对象和 helper。它不负责实现 heuristic 本身，只负责生成 Rust solver 已支持的配置结构。

### 2.1. Config 主对象

`Config` 负责从默认配置或 raw dict 构造 solver config，设置 termination、parallelism 以及演化配置（initial/recreate/population/hyper 等）。

**扩展规则**：
1. 方法名体现 schema 语义，例如 `set_termination`、`set_population_rosomaxa`。
2. 参数使用 Python 友好命名，但输出 JSON 字段必须与 solver schema 一致。
3. 对可选字段只在非 `None` 时写入，方法返回 `self`，便于链式配置。

### 2.2. Objective Helper

`Objective` 用于构造 pragmatic objectives，例如 `minimize_cost()`、`minimize_unassigned()`、`minimize_tours()`、`balance_max_load()` 等。新增 objective helper 时需要确认 pragmatic objective `type` 名称，如果存在 options，需保持 schema 要求的字段结构，并添加测试。

### 2.3. Ruin-Recreate、Population 与 Hyper

* **`Recreate`**：描述重建策略（cheapest、farthest、regret、skip-best 等）。
* **`Ruin`**：描述破坏策略（random、neighbour、worst、cluster、group 等）。
* **`LocalOperator` 与 `Hyper`**：`LocalOperator` 描述 local search operator，`Hyper` 将 local search、ruin-recreate 等方法组合为 hyper heuristic 配置。

---

## 3. Solve 流程、Native Binding 与结果模块

该模块负责把 Python facade 与 Rust solver 连接起来。Python 层负责输入归一化、校验、callback 包装和结果对象化；Rust binding 负责调用真正的 solver、checker、converter 和 serializer。

### 3.1. solve 主流程

`solve(...)` 的标准流程：
1. 将 `problem` 归一化为 `Problem`，`matrices` 归一化为 `RoutingMatrix` 列表，`config` 归一化为 `Config`。
2. 如传入 `initial_solution`，归一化为 `InitialSolution`。
3. 执行 Python 侧基础校验（维度、必填项）。
4. 序列化为 JSON 字符串。
5. 根据 initial solution 和 callback 组合选择 native binding。
6. 将 native 返回的 JSON 包装为 `Solution`。

### 3.2. Native binding 路径选择

根据参数组合选择底层不同的 native binding 导出函数：

| 场景 | Native function |
| --- | --- |
| 无初始解、无回调 | `solve_pragmatic` |
| 有初始解、无回调 | `solve_pragmatic_with_init` |
| 无初始解、有回调 | `solve_pragmatic_with_callback` |
| 有初始解、有回调 | `solve_pragmatic_with_init_and_callback` |

### 3.3. Callback 契约

Python callback 签名为 `def on_iteration(generation: int, solution: Solution) -> None`。
Rust binding 内部回传 generation 和 solution JSON，Python facade 转换为 `Solution` 快照。扩展时保证 `every > 0`，并捕获回调异常抛回调用者。

### 3.4. Validation 与 Checker

* **`validate`**：调用 native pragmatic validator，求解前验证 schema 极其一致性。
* **`check`**：调用 native solution checker，返回 `CheckResult`。`bool(result)` 表示是否可行，`raise_if_infeasible()` 在不可行时抛出明细异常。

### 3.5. Converter 与 Locations

* **`convert_to_pragmatic`**：调用 native converter 把外部科学格式内容转换成 `Problem`。
* **`get_locations`**：返回去重的 `RoutingLocations`。

### 3.6. Solution 与 View 对象

* **`Solution`**：封装 solver 输出。新增 accessor 时应保持兼容字段缺失，不修改内部 solution JSON，返回深拷贝。
* **`TourView` 与 `StopView`**：View 对象用于结构化地访问 solution。对于缺失字段应返回 `None` 或空列表，避免 KeyError。

---

## 4. PyO3 扩展规范

在二次开发修改 Rust FFI 边界或新增 Python 绑定时：
1. 使用 `#[pyfunction]` 暴露 Rust 函数。
2. 在 `vrp-cli/src/lib.rs` 的 module init 中 `m.add_function(...)` 注册。
3. 将 Rust error 转换为 `PyOSError` 或更合适的 Python exception。
4. 如果函数接收 JSON，参数类型优先为 `String`。
5. 如果函数返回 structured data，优先返回 JSON string，交给 Python facade 包装。
6. 为 binding 添加 Rust 编译检查和 Python 调用测试。

---

## 5. 测试建议

| 开发改动 | 测试重点 |
| --- | --- |
| 新增 Builder 方法 | 成功序列化测试、缺失参数校验、与 solve 集成测试。 |
| Config Helper | `to_dict()` 字段对齐测试、链式合并测试、用户 raw dict 混合测试。 |
| `solve` 入口参数 | 四条 native 路径兼容性、callback 触发与异常传播。 |
| Checker / Converter | 异常输入测试、feasible 判定、返回值包装测试。 |
| PyO3 binding | `cargo check --features py_bindings` 编译和 Python unittest。 |
