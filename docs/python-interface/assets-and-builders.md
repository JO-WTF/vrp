# 数据资产与 Builder 模块

## 文档信息

| 项目 | 内容 |
| --- | --- |
| 文档类型 | 模块设计与二次开发说明 |
| 适用模块 | `JsonAsset`, `Problem`, `RoutingLocations`, `RoutingMatrix`, `MatrixCollection`, `InitialSolution` |
| 主要源码 | `vrp-cli/python/vrp_cli/__init__.py` |
| 目标读者 | 需要新增 problem/matrix/initial-solution helper 的开发者 |

## 1. 设计目标

数据资产层的核心目标是让 Python 用户用对象和 builder 完成 pragmatic JSON 的构造，同时保证所有对象最终仍可无损序列化为 Rust solver 接收的 JSON。该层不应重新定义 VRP 求解语义，只负责输入数据的组织、轻量校验和用户体验。

## 2. 通用资产契约：`JsonAsset`

### 2.1 职责

`JsonAsset` 是 problem、matrix、config、solution 等对象的基础抽象，提供统一的 JSON 读写能力：

- `from_json(source)`：从路径、JSON 字符串或 JSON-like 输入构造。
- `from_dict(data)`：从 Python dict/list 构造。
- `to_dict()`：返回深拷贝，保护内部状态。
- `to_json(**kwargs)`：序列化为 JSON 字符串。
- `write_json(path, **kwargs)`：写入磁盘。

### 2.2 扩展规则

新增资产类时建议：

1. 继承 `JsonAsset`，除非对象不是 JSON 资产。
2. 在构造函数中将 dataclass、pydantic model、path-like 等输入转换为 JSON-compatible dict/list。
3. 对外返回深拷贝，避免用户绕过 builder 修改 `_data`。
4. 保持 `from_json` 和 `from_dict` 的行为一致。

## 3. Problem 模块

### 3.1 职责

`Problem` 表示 pragmatic problem definition，负责：

- 创建空 problem skeleton。
- 添加 delivery、pickup、pickup-delivery、service/replacement 等 job/task 结构。
- 添加 vehicle、profile、shift、capacity、cost、time window 等字段。
- 管理 relation、objective 等 pragmatic 扩展结构。
- 执行 Python 侧基础校验。
- 调用 native validation 或 locations extraction。

### 3.2 Builder 设计约定

Problem builder 方法应符合以下约定：

| 约定 | 说明 |
| --- | --- |
| 链式返回 | 修改当前 problem 后返回 `self`，便于 `Problem.empty().add_vehicle(...).add_delivery(...)`。 |
| 显式常用字段 | 对常用字段提供命名参数，例如 `location`, `demand`, `duration`, `times`, `capacity`。 |
| 透传扩展字段 | 对尚未建模的 pragmatic 字段允许 `**extra` 或 raw dict。 |
| 统一 location 形态 | 复用 `_location`，允许 index、coordinate dict 或已成型 location dict。 |
| 保留 task type | pickup/delivery/service/replacement 不应在 builder 中混淆，便于 metadata 和可视化识别。 |

### 3.3 校验层级

Problem 相关校验分三层：

1. **Python 快速校验**：例如至少有一个 vehicle/job、capacity 与 demand 维度一致。
2. **矩阵一致性校验**：profile 是否存在、矩阵长度是否等于 location 数量平方。
3. **Native pragmatic validation**：最终调用 Rust validator，作为权威校验结果。

二次开发时不要把复杂业务规则完全复制到 Python 层。Python 层只应提供更早、更易理解的错误提示。

### 3.4 新增 builder 模板

```python
def add_xxx(self, job_id: str, ..., **extra: Any) -> "Problem":
    task = _task(location, demand, duration=duration, times=times, tag=tag)
    job = {"id": job_id, "services": [task]}
    job.update(extra)
    self._jobs().append(job)
    return self
```

实现后需要补充：

- 成功序列化测试。
- 缺失关键参数或维度不一致测试。
- 至少一个示例或 README 片段。

## 4. RoutingLocations 与 RoutingMatrix

### 4.1 `RoutingLocations`

`RoutingLocations` 表示 native 提取出的有序去重地点列表。二次开发者不应在 Python 层自行推导 location 顺序，因为 Rust solver 和 matrix index 对顺序敏感。

推荐流程：

```python
locations = problem.get_locations()
# 使用 locations 调用外部 routing engine
# 再按相同顺序构造 RoutingMatrix
```

### 4.2 `RoutingMatrix`

`RoutingMatrix` 对 pragmatic matrix 做 Python 友好封装：

- Python 入参使用 `durations` 表示时间矩阵。
- 序列化时转换为 pragmatic 字段 `travelTimes`。
- 支持 `distances`、`profile`、`timestamp`。
- 支持从二维矩阵展平。

### 4.3 矩阵扩展注意事项

- `durations` 和 `distances` 长度必须一致。
- 如果 problem 中有 `n` 个 unique locations，则一维矩阵长度应为 `n * n`。
- 多 profile 场景下，matrix `profile` 必须在 problem profiles 中存在。
- time-dependent 场景下，应明确 `timestamp` 的语义并保持与 solver schema 一致。

## 5. MatrixCollection

`MatrixCollection` 用于将多个 `RoutingMatrix` 组合后传给 solver。扩展时需注意：

- solver 接收的是矩阵列表，而不是嵌套 collection JSON。
- collection 应保持插入顺序稳定。
- 如果未来支持按 profile/timestamp 查询，应避免破坏现有 list-like 行为。

## 6. InitialSolution

### 6.1 职责

`InitialSolution` 表示传入 solver 的初始路线，用于 warm start 或固定部分路线。它应保持与 pragmatic initial solution schema 兼容。

### 6.2 二次开发规则

- 支持从 raw JSON 加载，避免阻断高级用户。
- 支持从 `Solution` 或 tour-like Python 数据结构构造。
- 不在 Python 层做复杂可行性证明，最终仍由 solver/checker 判断。
- 新增 helper 时要说明输入 stop/activity 的最小字段要求。

## 7. 常见扩展场景

| 场景 | 推荐改动 | 测试重点 |
| --- | --- | --- |
| 新增 job 类型 helper | `Problem` 新增 builder | JSON 结构、metadata、solver validation。 |
| 新增 vehicle shift 字段 | `add_vehicle` 或独立 shift helper | 字段透传、默认值、向后兼容。 |
| 支持新 location 输入形态 | `_location` 私有工具 | 所有 builder 的 location 序列化。 |
| 新增矩阵构造方法 | `RoutingMatrix` classmethod | 展平顺序、长度校验、`travelTimes` 输出。 |
| 新增 initial solution 构造器 | `InitialSolution` classmethod | 与 `solve(..., initial_solution=...)` 集成。 |
