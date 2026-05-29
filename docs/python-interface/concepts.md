# 2. Concepts

## 2.1. Pragmatic format in Python

Python Interface 以原 Rust 项目的 pragmatic format 为核心数据模型。区别是用户可以不直接编写完整 JSON，而是用 Python asset 和 builder 生成等价结构。

| Pragmatic 组成 | Python Interface 对象 | 说明 |
| --- | --- | --- |
| `plan` | `Problem` builder | 描述 jobs、relations、clustering 等工作计划。 |
| `fleet` | `Problem.add_vehicle`, profile/raw dict | 描述 vehicle types、shifts、profiles、resources。 |
| `objectives` | `Objective` 或 raw dict | 描述优化目标。 |
| routing matrix | `RoutingMatrix`, `MatrixCollection` | 描述 travel time 和 distance。 |
| config | `Config` 和 heuristic helpers | 描述 solver termination、population、initial、hyper。 |
| solution | `Solution` | 描述 tours、statistic、unassigned、violations/geojson。 |

所有 asset 都围绕同一原则设计：Python 层提升可用性，序列化结果仍是 native solver 可识别的 pragmatic JSON。

## 2.1.1. Modeling a problem

一个 problem 通常由三部分组成：

- `plan`：需要车辆执行的工作，例如 jobs、relations、clustering。
- `fleet`：可用车辆和 routing profiles。
- `objectives`：可选，描述优化目标。

Python 中可以通过以下方式构造：

```python
problem = Problem.empty()
problem.add_delivery("job_1", (52.5, 13.4), [1])
problem.add_vehicle(
    "vehicle_1",
    start_location=(52.5, 13.3),
    start_earliest="2019-07-04T09:00:00Z",
    capacity=[10],
)
```

也可以直接加载完整 pragmatic JSON：

```python
problem = Problem.from_json("problem.json")
```

## 2.1.1.1. Jobs

Job 是 solver 需要安排的工作。Python Interface 当前主要提供以下 job builder：

| Builder | 适用业务 | 核心参数 |
| --- | --- | --- |
| `add_delivery` | 配送任务 | `job_id`, `location`, `demand`, `duration`, `times` |
| `add_pickup` | 取货任务 | `job_id`, `location`, `demand`, `duration`, `times` |
| `add_pickup_delivery` | 成对取送 | `pickup_location`, `delivery_location`, `demand` |

常用字段：

- `location`：可以是 `(lat, lng)` 或 pragmatic location dict。
- `demand`：整数数组，支持多维 capacity。
- `duration`：服务时间。
- `times`：一个或多个 time windows。
- `tag` / `order`：用于更细粒度标识和排序。
- `**extra`：透传 pragmatic schema 中尚未封装的字段。

示例：

```python
problem.add_delivery(
    "delivery_1",
    (52.52599, 13.45413),
    [1],
    duration=300,
    times=[["2019-07-04T09:00:00Z", "2019-07-04T18:00:00Z"]],
    priority=1,
)
```

## 2.1.1.2. Vehicles

Vehicle 描述可用资源类型及其 shifts。Python 中通过 `add_vehicle` 添加：

```python
problem.add_vehicle(
    "vehicle_1",
    type_id="vehicle",
    profile="normal_car",
    start_location=(52.5316, 13.3884),
    start_earliest="2019-07-04T09:00:00Z",
    end_location=(52.5316, 13.3884),
    end_latest="2019-07-04T18:00:00Z",
    capacity=[10],
    costs={"fixed": 22, "distance": 0.0002, "time": 0.005},
)
```

关键概念：

- vehicle type 可以代表一组车辆，而不一定是一辆具体车。
- `vehicle_ids` 可用于生成多个具体 vehicle id。
- `profile` 需要与 routing matrix 的 `profile` 对应。
- `capacity` 与 job `demand` 维度必须一致。
- shift 的 start/end time 会限制可服务时间范围。

## 2.1.1.3. Resources

Resources 包括 break、reload、recharge、车辆 shift 资源点等。Python builder 对常见 vehicle 字段提供直接参数；复杂 resources 可通过 raw dict 或 `**extra` 注入。

建议策略：

1. 简单资源优先使用 builder 参数。
2. 复杂资源保留 pragmatic 原始结构。
3. 添加后运行 `validate(problem, matrices)`。
4. 如果资源要展示在 VRP Studio 中，需要确保 location 字段可被 metadata 提取。

## 2.1.1.4. Relations

Relations 用于约束 jobs 与 vehicle 的关系，例如锁定某些 job 到指定车辆、要求 job 顺序或允许某组 job 任意顺序。

Python Interface 支持用 helper 或 raw pragmatic relation 配置。典型使用方式是：

```python
# 伪代码：具体 relation helper 以当前 facade 实现为准
problem.add_relation(
    type="sequence",
    jobs=["pickup_1", "delivery_1"],
    vehicle_id="vehicle_1",
)
```

二次开发 relation helper 时，应保证：

- relation type 与 pragmatic schema 一致。
- job id 和 vehicle id 不被自动改写。
- raw relation dict 仍可直接传入。

## 2.1.1.5. Clustering

Clustering 用于把相近或相关 jobs 组合起来，减少不现实的 ETA 或提升路线结构质量。Python Interface 当前以兼容 pragmatic schema 为主，复杂 clustering 配置建议直接使用 raw JSON：

```python
problem_dict = problem.to_dict()
problem_dict["plan"]["clustering"] = {...}
problem = Problem.from_dict(problem_dict)
```

如果未来新增 clustering builder，应遵循 `Problem` builder 规则：链式返回、字段透传、native validation 为准。

## 2.1.1.6. Objectives

Objectives 描述 solver 的优化目标。Python 中可使用 `Objective` helper：

```python
from vrp_cli import Objective

objectives = [
    Objective.minimize_cost().to_dict(),
    Objective.minimize_unassigned().to_dict(),
    Objective.balance_distance(threshold=0.1).to_dict(),
]
```

常见目标：

- minimize cost。
- minimize unassigned。
- minimize tours / maximize tours。
- maximize value。
- minimize distance / duration / arrival time。
- balance max load / activities / distance / duration。

如目标尚未封装，可直接使用 raw dict，只要 native solver 支持对应 schema。

## 2.1.2. Routing data

Routing data 连接 problem location 与 solver routing cost。Python Interface 中最重要的对象是 `RoutingMatrix`。

### Routing matrix

一维矩阵按 locations 顺序展平：

```python
matrix = RoutingMatrix(
    profile="normal_car",
    durations=[0, 609, 609, 0],
    distances=[0, 3840, 3840, 0],
)
```

二维矩阵：

```python
matrix = RoutingMatrix.from_2d(
    durations=[[0, 609], [609, 0]],
    distances=[[0, 3840], [3840, 0]],
    profile="normal_car",
)
```

### Profiles

如果 problem 使用多个 vehicle profile，则需要提供对应 profile 的矩阵：

```python
matrices = MatrixCollection()
matrices.add(car_matrix)
matrices.add(bike_matrix)
solution = solve(problem, matrices=list(matrices), config=config)
```

### Time-dependent matrix

`RoutingMatrix` 支持 `timestamp` 字段，用于表达某个时间点的 travel time/distance。使用时需要确保 solver config 和 problem 模型支持该语义。

## 2.1.3. Solution model

`Solution` 是求解结果的 Python facade。

### Tour list

```python
for tour in solution.iter_tours():
    print(tour.vehicle_id)
    for stop in tour.iter_stops():
        print(stop.location, stop.job_ids())
```

### Statistic

```python
stat = solution.statistic
print(stat.get("cost"))
print(stat.get("distance"))
print(stat.get("duration"))
print(stat.get("times", {}))
```

### Unassigned jobs

```python
for item in solution.unassigned:
    print(item.get("jobId"), item.get("reasons"))
```

### Violations

Violations 通常通过 checker 获取：

```python
result = check(problem, solution, matrices=[matrix])
if not result.is_feasible:
    for violation in result.violations:
        print(violation)
```

## 2.1.4. Error index and validation

Python Interface 有两类错误来源：

| 来源 | 典型错误 | 处理方式 |
| --- | --- | --- |
| Python facade | 缺少 vehicle/job、capacity 维度不一致、matrix 长度不匹配 | 修改 builder 输入或 matrix 构造。 |
| Native validator/solver | pragmatic schema 错误、不可解析配置、routing/profile 不一致、solution infeasible | 查看 native error message，回到 problem/config/matrix 修正。 |

推荐在求解前执行：

```python
problem.validate_problem()
problem.validate_matrices([matrix])
validate(problem, matrices=[matrix])
```

求解后执行：

```python
check(problem, solution, matrices=[matrix]).raise_if_infeasible()
```

## 2.2. Scientific formats

原 Rust 项目支持 Solomon、Li&Lim、TSPLIB 等科学/benchmark 格式。Python Interface 通过 `convert_to_pragmatic` 将外部格式转为 pragmatic `Problem`：

```python
from vrp_cli import convert_to_pragmatic

with open("problem.txt", "r", encoding="utf-8") as f:
    content = f.read()

problem = convert_to_pragmatic("solomon", [content])
problem.write_json("converted.problem.json", indent=2)
```

转换后仍按 pragmatic workflow 准备 matrix、config 并调用 `solve`。
