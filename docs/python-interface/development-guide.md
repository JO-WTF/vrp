# Python Interface 开发指南

## 文档信息

| 项目 | 内容 |
| --- | --- |
| 文档类型 | 二次开发指南 |
| 适用模块 | `vrp-cli/python`, `vrp-cli/src/lib.rs`, `examples/python-interop`, `vrp-cli/python/tests` |
| 主要目标 | 说明开发环境、代码组织、扩展步骤、测试矩阵和文档维护要求 |
| 前置阅读 | `docs/python-interface.md` |

## 1. 模块边界

Python interface 由四类代码共同构成：

| 层级 | 主要路径 | 职责 |
| --- | --- | --- |
| Python facade | `vrp-cli/python/vrp_cli/__init__.py` | 面向 Python 用户的 public API、builder、typed helper、输入归一化、轻量校验。 |
| 可视化辅助 | `vrp-cli/python/vrp_cli/vis/` | 求解轨迹记录、job metadata 提取、轻量静态服务。 |
| Native binding | `vrp-cli/src/lib.rs` | 通过 PyO3 暴露 Rust solver/checker/converter 等能力。 |
| 示例与测试 | `examples/python-interop/`, `vrp-cli/python/tests/` | 固定用法、回归行为和接口契约。 |

二次开发时应先判断需求属于哪一层：

- 只是让 Python 更好用：优先改 Python facade。
- 需要调用 Rust 已有函数：扩展 PyO3 binding。
- 需要改变求解语义：进入 Rust core 或 pragmatic 模块，而不是在 Python 层绕过。
- 需要展示新数据：扩展 `Solution` accessor、tracker history 或 VRP Studio 数据消费。

## 2. 开发环境

### 2.1 基础依赖

- Python 3.10+
- Rust stable toolchain
- `maturin`
- 可选：`uv`，用于 workspace 内 Python 包安装和运行

### 2.2 本地安装 binding

开发 Python facade 并需要真实 native 调用时，推荐在仓库根目录或 `vrp-cli` 包上下文执行：

```bash
maturin develop --features py_bindings
```

构建 release wheel：

```bash
maturin build --release --features py_bindings
```

只验证 Rust/PyO3 编译：

```bash
cargo check --features py_bindings
```

## 3. 代码组织规范

### 3.1 Python facade 组织

`vrp_cli/__init__.py` 当前集中定义 public API。新增内容时建议遵循现有顺序：

1. 通用类型别名与 `JsonAsset`。
2. problem/matrix/config 等输入资产。
3. heuristic typed helper。
4. initial solution 和 solution/result view。
5. `solve`、`validate`、`check`、`convert_to_pragmatic` 等函数入口。
6. 私有工具函数。

### 3.2 Public API 设计约束

新增 public API 时应满足：

- **JSON-compatible**：输出必须能被 `json.dumps` 序列化。
- **链式体验一致**：builder 类方法优先返回 `self` 或明确的新 asset。
- **原始 schema 可透传**：复杂 schema 字段应允许用户传入 raw dict 或 `**extra`。
- **错误信息可定位**：Python 侧校验应指出 job id、vehicle type、matrix index 等上下文。
- **不隐藏 native 错误**：Rust binding 抛出的解析、校验、求解错误应向调用者暴露。

### 3.3 Native binding 设计约束

扩展 PyO3 binding 时应遵循：

- Python 入参尽量使用字符串或简单 list，保持边界清晰。
- 复杂对象由 Python facade 负责序列化为 JSON。
- Rust binding 返回 JSON 字符串，由 Python facade 再包装为 asset。
- callback 路径需要捕获 Python 异常，并在 solver 返回后重新抛出，避免吞掉回调错误。

## 4. 推荐扩展流程

### 4.1 新增 Problem builder

1. 在 `Problem` 上新增方法，内部生成 pragmatic schema 片段。
2. 复用 `_location`、`_task`、`_set_if_not_none` 等私有工具。
3. 保持链式返回 `self`。
4. 添加 Python 单元测试，验证 `to_dict()` 和 `to_json()` 结构。
5. 添加一个 `examples/python-interop` 示例或更新现有示例。
6. 更新 `assets-and-builders.md` 和总览速查表。

### 4.2 新增 Config/heuristic helper

1. 确认 Rust/pragmatic config schema 已支持对应字段。
2. 在 `Config` 或 typed helper 类中新增 constructor/setter。
3. 返回普通 dict 或 dict subclass，便于用户混合 raw JSON。
4. 添加序列化测试和至少一个组合配置测试。
5. 更新 `config-and-heuristics.md`。

### 4.3 新增 native 能力

1. 先在 Rust 层确认已有函数或新增核心实现。
2. 在 PyO3 module 中添加 `#[pyfunction]`。
3. 在 Python facade 中添加薄包装，完成 asset 转换。
4. 覆盖成功路径和错误路径测试。
5. 更新 `solve-bindings-and-results.md`。

### 4.4 新增可视化字段

1. 判断字段来自 problem metadata、solution statistic、tour stop 还是 unassigned item。
2. 在 `Solution` accessor 或 `SolveTracker._record` 中输出。
3. 保持 history JSON 向后兼容，新增字段应允许前端缺省。
4. 添加 tracker 输出结构测试。
5. 更新 `visualization-tracker.md`。

## 5. 测试矩阵

| 改动类型 | 必跑测试/检查 | 说明 |
| --- | --- | --- |
| 仅 Markdown | Markdown 基础检查或人工 review | 确认链接、标题层级、命令示例正确。 |
| Python facade 序列化 | `python -m unittest discover -s vrp-cli/python/tests` | 不一定需要真实求解，但要覆盖 JSON 结构。 |
| Native binding | `cargo check --features py_bindings` | 确认 PyO3 编译通过。 |
| 真实求解路径 | facade integration test 或示例脚本 | 验证 Rust solver 可接收 facade 输出。 |
| examples 变更 | 运行对应 example | 确保文档中的示例可复制。 |
| 可视化 tracker | tracker 单测 + 小 problem 回调 | 验证 history JSON 字段稳定。 |

## 6. 文档维护要求

每次新增 public API 时至少更新以下位置之一：

- `docs/python-interface.md`：总览、速查表或二次开发流程。
- 对应细分文档：模块契约、扩展步骤、测试建议。
- `examples/python-interop/README.md` 或示例脚本：面向用户的最小用法。

文档示例中的 API 名称必须与代码一致；如果示例需要 native binding，需注明需要先执行 `maturin develop --features py_bindings`。
