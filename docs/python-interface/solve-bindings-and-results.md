# Solve、Native Binding 与结果模块

## 文档信息

| 项目 | 内容 |
| --- | --- |
| 文档类型 | 模块设计与二次开发说明 |
| 适用模块 | `solve`, `validate`, `check`, `convert_to_pragmatic`, `Solution`, `TourView`, `StopView`, `CheckResult`, PyO3 binding |
| 主要源码 | `vrp-cli/python/vrp_cli/__init__.py`, `vrp-cli/src/lib.rs` |
| 目标读者 | 需要扩展求解入口、native binding、callback 或结果访问能力的开发者 |

## 1. 设计目标

该模块负责把 Python facade 与 Rust solver 连接起来。Python 层负责输入归一化、轻量校验、callback 包装和结果对象化；Rust binding 负责调用真正的 solver、checker、converter 和 serializer。

## 2. solve 主流程

`solve(...)` 的标准流程：

1. 将 `problem` 归一化为 `Problem`。
2. 将 `matrices` 归一化为 `RoutingMatrix` 列表。
3. 将 `config` 归一化为 `Config`，缺省时提供默认 termination。
4. 如传入 `initial_solution`，归一化为 `InitialSolution`。
5. 执行 Python 侧基础校验：problem、config、matrix 维度。
6. 序列化为 JSON 字符串。
7. 根据 initial solution 和 callback 组合选择 native binding。
8. 将 native 返回的 JSON 包装为 `Solution`。

## 3. Native binding 路径选择

| 场景 | Native function |
| --- | --- |
| 无初始解、无回调 | `solve_pragmatic` |
| 有初始解、无回调 | `solve_pragmatic_with_init` |
| 无初始解、有回调 | `solve_pragmatic_with_callback` |
| 有初始解、有回调 | `solve_pragmatic_with_init_and_callback` |

二次开发新增 `solve` 参数时，必须检查四条路径是否都需要传递该参数。如果参数只影响 config，优先写入 `Config`，避免扩展所有 native function signature。

## 4. Callback 契约

Python callback 形态：

```python
def on_iteration(generation: int, solution: Solution) -> None:
    ...
```

Rust binding 内部回传 generation 和 solution JSON；Python facade 再转换为 `Solution`。扩展 callback 时需要注意：

- `every` 必须大于 0。
- Python callback 抛出的异常不能静默丢失，应在求解结束后抛回调用者。
- callback 中的 `Solution` 应被视为只读快照。
- 可视化和 tracker 应避免每代都写入大量数据，建议只记录 new best 或按间隔采样。

## 5. Validation 与 Checker

### 5.1 `validate`

`validate(problem, matrices)` 调用 native pragmatic validator。它适合在求解前验证输入 schema、矩阵与 problem 的一致性。

### 5.2 `check`

`check(problem, solution, matrices)` 调用 native solution checker，返回 `CheckResult`。`CheckResult` 应保持以下行为：

- `is_feasible` 表示是否没有 violations。
- `violations` 保存可读错误列表。
- `bool(result)` 等价于 `result.is_feasible`。
- `len(result)` 返回 violations 数量。
- `raise_if_infeasible()` 在不可行时抛出带明细的 `ValueError`。

新增 checker 结果字段时，应保持这些既有行为向后兼容。

## 6. Converter 与 Locations

### 6.1 `convert_to_pragmatic`

该函数把外部格式内容转换成 `Problem`。扩展新格式时的顺序：

1. Rust converter 支持该格式。
2. PyO3 binding 暴露格式参数。
3. Python facade 返回 `Problem`。
4. 示例中展示输入文件读取和转换结果保存。

### 6.2 `get_locations`

`get_locations(problem)` 返回 `RoutingLocations`。matrix 生成必须使用该顺序，否则 solver 会把 matrix index 解释到错误地点。

## 7. Solution 与 View 对象

### 7.1 Solution

`Solution` 封装 solver 输出，常用访问包括：

- 总成本。
- statistic。
- tours。
- unassigned。
- GeoJSON。

新增 accessor 时应：

- 兼容字段缺失。
- 不修改内部 solution JSON。
- 对 list/dict 返回深拷贝或只读 view。
- 在测试中覆盖空 solution、无 unassigned、无 statistic 等场景。

### 7.2 TourView 与 StopView

View 对象用于更结构化地 inspection solution。扩展时建议：

- 保持轻量，不复制大对象过多。
- 明确 vehicle id、stop location、activities、arrival/departure 等字段来源。
- 对缺失字段返回 `None` 或空列表，而不是抛出难以定位的 KeyError。

## 8. PyO3 扩展规范

新增 PyO3 function 时：

1. 使用 `#[pyfunction]` 暴露 Rust 函数。
2. 在 module init 中 `m.add_function(...)` 注册。
3. 将 Rust error 转换为 `PyOSError` 或更合适的 Python exception。
4. 如果函数接收 JSON，参数类型优先为 `String` 或 `Vec<String>`。
5. 如果函数返回 structured data，优先返回 JSON string，交给 Python facade 包装。
6. 为 binding 添加 Rust 编译检查和 Python 调用测试。

## 9. 测试建议

| 改动类型 | 测试重点 |
| --- | --- |
| `solve` 参数 | 四条 native 路径是否保持行为一致。 |
| callback | `every` 校验、异常传播、solution 包装。 |
| `Solution` accessor | 缺失字段、深拷贝、防止修改原始数据。 |
| checker | feasible/infeasible、`bool`、`len`、`raise_if_infeasible`。 |
| converter | 输入格式错误、转换成功、返回 `Problem`。 |
| PyO3 binding | `cargo check --features py_bindings` 和 Python smoke test。 |
