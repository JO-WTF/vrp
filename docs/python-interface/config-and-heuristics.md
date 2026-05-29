# Config 与 Heuristic Helper 模块

## 文档信息

| 项目 | 内容 |
| --- | --- |
| 文档类型 | 模块设计与二次开发说明 |
| 适用模块 | `Config`, `Objective`, `Recreate`, `Ruin`, `Population`, `Probability`, `LocalOperator`, `Hyper`, `noise`, `min_max` |
| 主要源码 | `vrp-cli/python/vrp_cli/__init__.py` |
| 目标读者 | 需要新增求解配置、heuristic preset 或 typed helper 的开发者 |

## 1. 设计目标

配置模块的目标是把 solver config JSON 转换成 Python 可组合的对象和 helper。它不负责实现 heuristic 本身，只负责生成 Rust solver 已支持的配置结构。

原则：

- 保持 raw JSON 兼容，开发者可以随时传入 dict。
- typed helper 只降低使用成本，不隐藏底层 schema。
- helper 输出应可组合、可序列化、可测试。
- 新增配置必须与 Rust solver/pragmatic config schema 对齐。

## 2. Config 主对象

### 2.1 职责

`Config` 负责：

- 从默认配置或 raw dict 构造 solver config。
- 设置 termination，例如 max time、max generations、variation。
- 设置 parallelism。
- 设置 initial/recreate/population/hyper 等演化配置。
- 合并 preset 与用户 override。

### 2.2 扩展规则

新增 `Config` 方法时建议：

1. 方法名体现 schema 语义，例如 `set_termination`、`set_population_rosomaxa`。
2. 参数使用 Python 友好命名，但输出 JSON 字段必须与 solver schema 一致。
3. 对可选字段只在非 `None` 时写入。
4. 方法返回 `self`，便于链式配置。
5. 如果配置片段较复杂，提供 typed helper 而不是要求用户传入深层 dict。

### 2.3 合并策略

Config 合并应保持“用户显式配置优先”：

- preset 提供默认结构。
- 用户传入的 max time、generations、parallelism 等 override 覆盖 preset。
- typed helper 返回的 dict 可以与 raw JSON 混合。

## 3. Objective Helper

`Objective` 用于构造 pragmatic objectives，例如：

- `minimize_cost()`
- `minimize_unassigned()`
- `minimize_tours()` / `maximize_tours()`
- `maximize_value()`
- `minimize_distance()` / `minimize_duration()` / `minimize_arrival_time()`
- `balance_max_load()` / `balance_activities()` / `balance_distance()` / `balance_duration()`

新增 objective helper 时：

1. 确认 pragmatic objective `type` 名称。
2. 如果存在 options，保持 `{ "options": ... }` 或 schema 要求的字段结构。
3. 添加 `to_dict()` 断言测试。
4. 在 examples 中展示与 `Problem` 或 config 的组合方式。

## 4. Ruin-Recreate Helper

### 4.1 Recreate

`Recreate` 描述重建策略，例如 cheapest、farthest、regret、skip-best 等。新增策略时需要明确：

- `type` 名称。
- `weight` 默认值。
- 特有参数，例如 regret 的阶数或 skip-best 范围。
- 是否支持 noise。

### 4.2 Ruin

`Ruin` 描述破坏策略，例如 random、neighbour、worst、cluster、group 等。新增策略时需要明确：

- 作用对象和范围。
- 参数单位，例如数量、比例、距离或邻域大小。
- 是否可嵌套到 group。

### 4.3 组合规则

ruin-recreate helper 应输出普通 dict 或 dict subclass。这样用户可以：

```python
config = Config.defaults().set_hyper_static([
    Hyper.ruin_recreate(
        ruins=[Ruin.group([Ruin.neighbour(1, 8, 16)], weight=10)],
        recreates=[Recreate.cheapest(weight=20)],
    )
])
```

## 5. Population Helper

Population helper 用于描述 evolution population 类型。扩展时应注意：

- 与 Rust solver 已支持类型保持一致。
- 参数名尽量使用 Python snake_case，输出时转换为 schema 字段。
- 对 rosomaxa 等高级配置，应保留 raw options 入口，避免 helper 落后于 solver schema。

## 6. LocalOperator 与 Hyper

### 6.1 LocalOperator

`LocalOperator` 描述 local search operator。新增 operator 时：

- 提供 `weight` 参数。
- 如果支持 noise，复用统一 noise 结构。
- 对 operator 名称和 schema 字段添加测试。

### 6.2 Probability

`Probability` 用于描述静态或动态选择概率。扩展时需明确输出 JSON 形态，避免前端或示例误解概率含义。

### 6.3 Hyper

`Hyper` 将 local search、ruin-recreate 等方法组合为 hyper heuristic 配置。扩展时应提供：

- 方法类型。
- probability。
- times/min-max。
- operators、ruins、recreates 等子项。

## 7. 测试建议

| 测试类型 | 断言内容 |
| --- | --- |
| 单 helper 测试 | helper 返回 dict 与 schema 期望一致。 |
| Config 链式测试 | 多个 setter 连续调用后 JSON 合并正确。 |
| raw JSON 混合测试 | typed helper 与用户 raw dict 可一起使用。 |
| solver smoke test | 复杂 config 可被 native solver 接收。 |
| 示例回归 | `hyper_config.py`、`config_export.py` 等示例输出稳定。 |

## 8. 常见错误

- 在 Python 层发明 solver 不认识的字段。
- helper 返回不可 JSON 序列化的对象。
- setter 覆盖了用户已经设置的其他 config 分支。
- 参数命名未说明单位或范围。
- 新增 heuristic helper 但没有同步示例，导致用户不知道如何组合。
