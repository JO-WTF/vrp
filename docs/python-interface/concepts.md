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

Job 用于建模需要车辆执行的配送、取货或服务任务，并承载时间窗口、所需技能等业务约束。

### 任务类型与载重变化行为

不同类型的任务在车辆行驶过程中的**容量占用（Capacity Consumption）**变化逻辑不同：

* **配送任务 (Delivery Job)**：车辆在班次起点（仓库）装载货物，出车时车辆载重最高；到达配送地点后卸货，载重量相应减小（扣减 `demand`）。
* **取货任务 (Pickup Job)**：车辆出车时为空车或未装载该任务；到达取货地点后装货，载重量增加（累加 `demand`），货物会一直占用车辆容量，直到班次结束或车辆到达中途装货点（Reload）。
* **成对取送任务 (Pickup & Delivery Job)**：建模“从 A 地取货送至 B 地”的场景。求解器严格遵循以下规则：
  * **全有或全无**：要么两个任务全部完成，要么都不做（不能只取不送，或只送不取）。
  * **先后顺序**：车辆必须先访问取货点，再访问配送点。
  * **载重匹配**：取货任务的需求量总和必须等于配送任务的需求量总和。
* **服务任务 (Service Job)**：用于建模不需要装载货物的上门工作（如设备巡检、安装维修）。无货物容量占用（`demand` 为零），车辆仅在地点停留 `duration` 时长。
* **多备选地点任务 (Multi-place Task)**：通过 `add_multi_place_task` 配置，当一个任务有多个可供选择的地点或自提柜时，求解器会自动选择最合适的一个地点访问并进行服务。

### 核心概念：Tasks 与 Places

在 Pragmatic 格式中，一个 Job 包含一组 **Tasks**（如 pickups、deliveries 或 services），每个 Task 下又包含一组 **Places**：
* **Task 规则**：在成对取送或混合任务中，一个 Job 包含多个 Task 时，这些 Task 必须属于同一个 Tour，要么一起完成，要么一起被标记为 unassigned。
* **Place 规则**：每个 Task 下可以定义一个或多个 `place`。每个 `place` 包含位置 `location`、服务时长 `duration`、可选的时间窗口 `times` 和标识标签 `tag`。当包含多个备选 Place 时，求解器将执行**多选一**的优化决策。

### 属性配置与约束规则

* **时间窗口的硬性特征 (Time Windows)**：Job 的 `times` 是**硬性约束**。如果由于行驶距离、速度、工作时长等限制导致所有车辆都无法在规定的时间窗口内到达任务点，求解器将放弃该任务，将其归类为“未分配任务”（unassigned），并在 `Solution` 中附带失败原因代码。
* **优先级 (Priority)**：`set_job_priority(job_id, priority)` 用于指导求解顺序（`1` 代表最高优先级）。
* **技能资质 (Skills)**：`set_job_skills(job_id, ...)` 限制只有具备对应技能的车辆（如冷链、化学品运输资质）才能承接此任务。支持 `allOf`（全部具备）、`oneOf`（具备其一）、`noneOf`（不能具备）。
* **任务价值 (Value)**：`set_job_value(job_id, value)` 赋予任务经济价值，配合 `maximize-value` 优化目标可以使求解器优先拉运高价值任务。
* **分组与兼容性 (Group & Compatibility)**：
  * `set_job_group(job_id, group)`：将相同 group 的任务强绑定在同一条路线中。
  * `set_job_compatibility(job_id, compatibility)`：防止混装（例如不能同时在一个 Tour 内拉运危险品与食品）。

### Job Builders 快速参考

| Builder 方法 | 载重行为 | 核心参数 |
| --- | --- | --- |
| `add_delivery` | 出发时占用容量，送达后减少 | `job_id`, `location`, `demand`, `duration`, `times`, `tag`, `order` |
| `add_pickup` | 收集后载重增加，占用至结束 | `job_id`, `location`, `demand`, `duration`, `times`, `tag`, `order` |
| `add_pickup_delivery` | 先取后送，载重匹配，全有或全无 | `job_id`, `pickup_location`, `delivery_location`, `demand`, `pickup_duration`, `delivery_duration` |
| `add_service` | 载重零消耗，仅停留服务 | `job_id`, `location`, `duration`, `times`, `tag` |
| `add_multi_place_task` | 根据 task_type 决定，多选一位置 | `job_id`, `task_type` (`"pickups"` / `"deliveries"`), `places`, `demand`, `order` |

### 示例

```python
# 链式建模示例
problem = (
    Problem.empty()
    # 添加一个带有时间窗口和冷链资质要求的配送任务
    .add_delivery(
        "delivery_1",
        location=(52.52599, 13.45413),
        demand=[1],
        duration=300,
        times=[["2019-07-04T09:00:00Z", "2019-07-04T12:00:00Z"]]
    )
    .set_job_priority("delivery_1", priority=1)
    .set_job_skills("delivery_1", all_of=["cold_chain"])
    
    # 添加一个多备选点配送任务（如支持在两个不同侧门或自提点服务，多选一）
    .add_multi_place_task(
        "delivery_multi",
        task_type="deliveries",
        demand=[2],
        places=[
            {"location": {"lat": 52.526, "lng": 13.455}, "duration": 200},
            {"location": {"lat": 52.527, "lng": 13.456}, "duration": 400}
        ]
    )
)
```

## 2.1.1.2. Vehicles

Vehicle 用于描述可用车辆资源及其行驶班次（Shifts）和物理行驶限制。

### 基础定义

```python
problem.add_vehicle(
    "vehicle_1",
    type_id="vehicle_type_1",  # 车辆类型 ID
    vehicle_ids=["car_A", "car_B"],  # 该类型下的具体车辆 ID 列表，若只传入 vehicle_id，则默认单辆车
    profile="normal_car",  # 该车型对应的路由矩阵配置
    start_location=(52.5316, 13.3884),  # 班次起点位置
    start_earliest="2019-07-04T09:00:00Z",  # 最早出发时间
    end_location=(52.5316, 13.3884),  # 班次终点位置
    end_latest="2019-07-04T18:00:00Z",  # 最迟返回时间
    capacity=[10],  # 车型装载容量限制，需与 Job 需求量维度一致
    costs={"fixed": 22, "distance": 0.0002, "time": 0.005},  # 固定成本、距离成本与时间成本系数
)
```

### 核心概念：车型 (Vehicle Type) 与班次 (Shift)

在建模车辆资源时，需要理解以下核心规则：
* **车型 vs. 具体车辆**：`add_vehicle` 实际定义的是一个**车型（Vehicle Type）**。可以通过 `vehicle_ids` 列表指定该类型下有多少辆独立可用的物理车辆（求解器会为它们分配如 `car_A`、`car_B` 等具体 ID）。
* **班次时间硬约束 (Shift Times)**：车辆的时间窗口（由班次的 `start_earliest` 与 `end_latest` 决定）是**硬性限制**。所有分配给该车辆的 Job 必须在班次开始后出发，并在班次结束前返回。
* **多班次与多天建模**：每个车型默认包含一个 shift。可以通过 `add_vehicle_shift` 为其追加额外的班次。如果在同一车型上定义了多个不同日期/时间段的班次，求解器可以使同一辆车执行多次任务，这对于多天（multi-day）配送或多班次排班非常有用。

### 行驶控制与限制配置

* **开放式路线 (Open Loop)**：通过 `set_vehicle_open_end(vehicle_type_id)` 可以去除车辆返回终点的要求。车辆将留在最后一个任务地点结束任务，不计算回程的时间和距离成本。
* **最晚出发限制**：通过 `set_vehicle_dispatch(...)` 限制车辆优化出发时间时的最晚出发时间。
* **物理行驶限制 (Limits)**：
  - `set_vehicle_limits(vehicle_type_id, max_distance, max_duration, tour_size)` 设定车辆单次班次的最大行驶路程（`max_distance`）、最大总时间（`max_duration`，对应 schema 中的 `shiftTime`）以及单趟最多服务的任务活动数（`tour_size`）。超出限制的排线将被判定为不可行（infeasible）。
* **车辆资质 (Skills)**：通过 `set_vehicle_skills(...)` 赋予车辆特定资质，以满足部分 Job 的硬性资质匹配需求。
* **缩放因子与时速估算**：
  * `set_profile_scale(vehicle_type_id, scale)`：为具体车型设置耗时缩放系数（可用于模拟慢车或拥堵系数）。
  * `set_matrix_profile_speed(profile_name, speed)`：在不提供 `RoutingMatrix` 时，利用直线距离除以设定的时速（m/s）来估算 travel time。

## 2.1.1.3. Resources

Resources 用以定义车辆行驶过程中的补给、休息、装载等中途停靠点和共享资源。Python Interface 提供了对应的强类型 API：

* **中途休息 (Breaks)**：`add_vehicle_break(vehicle_type_id, times, duration, locations=None, shift_index=0)`。
  * `times` 为允许休息的多个时间窗口列表，如 `[["2019-07-04T12:00:00Z", "2019-07-04T14:00:00Z"]]`。
  * `locations` 为可选的允许休息的地点列表（若省略，车辆可以在行驶途中任意位置休息）。
* **中途装货点 (Reloads)**：`add_vehicle_reload(vehicle_type_id, location, duration=0, times=None, tag=None, shift_index=0)`。
  * 允许车辆中途返回指定的仓库地点进行补货并重新装满容量，从而可以在单次班次中服务总需求量超出车辆单次容量的任务。
* **补能站 (Recharge/Stations)**：`add_vehicle_recharge(vehicle_type_id, max_distance, stations, shift_index=0)`。
  * 用于给车辆配置中途的充电站或加油站。`max_distance` 限制了车辆两次充电之间的最大行驶里程，`stations` 为可用补能站点的列表。
* **共享装载资源 (Reload Resources)**：`add_vehicle_reload_resource(resource_id, capacity)`。
  * 用于在 Fleet 级别声明某种共享装载容量限制。

### 示例

```python
problem = (
    Problem.empty()
    # 为 vehicle_type_1 的车辆添加一个 30 分钟的中途休息约束
    .add_vehicle_break(
        "vehicle_type_1",
        times=[["2019-07-04T12:00:00Z", "2019-07-04T13:00:00Z"]],
        duration=1800
    )
    # 允许车型在中途的指定仓库地点补充装载
    .add_vehicle_reload(
        "vehicle_type_1",
        location=(52.5316, 13.3884),
        duration=600
    )
)
```

## 2.1.1.4. Relations

Relations 用于约束 jobs 与 vehicle 之间的关系，例如锁定某些 job 到指定车辆、要求指定 job 的服务顺序、或限定某组 job 必须在同一路线内服务（不限顺序）。

Python Interface 提供了四个强类型的 Relation 辅助配置函数：

* **顺序约束 (Sequence)**：`add_relation_sequence(jobs, vehicle_id)`。
  * 约束指定车辆必须按照 `jobs` 列表给定的顺序服务这些任务（允许中间插入其他任务）。
* **严格相邻顺序约束 (Strict)**：`add_relation_strict(jobs, vehicle_id, shift_index=None)`。
  * 约束指定车辆必须严格连续、且按照 `jobs` 列表给定的顺序服务这些任务（中间绝对不允许插入任何其他任务）。可以通过 `shift_index` 指定限制在特定班次上。
* **车辆绑定约束 (Tour)**：`add_relation_tour(jobs, vehicle_id)`。
  * 约束这一组 `jobs` 必须且仅能由指定的 `vehicle_id` 车辆服务（服务顺序任意）。
* **通用/自定义约束**：`add_relation(relation_type, jobs, vehicle_id, **extra)`。
  * 如果需要直接以特定类型（如 `type="any"`）或需要使用透传参数进行高级控制时，可调用此通用方法。

### 保留字支持

在 `jobs` 列表中，除常规的 Job ID 外，还支持使用特殊保留字来代表班次中的特定活动：
* **`departure`**：车辆班次起点
* **`arrival`**：车辆班次终点
* **`break`**：休息点
* **`reload`**：中途装载点

这可以用来建模更复杂的顺序，例如“在第一个 reload 装货点之后，必须立刻去送 job_1”：
```python
# 强制要求在 reload 之后紧邻配送 job_1
problem.add_relation_strict(jobs=["reload", "job_1"], vehicle_id="vehicle_1")
```

> [!CAUTION]
> **重要安全性说明**：在 Relation 中强制指定的关系，在求解前**不会**被求解器进行时间窗口、载重等硬性约束校验。如果用户配置了不合理的顺序（例如强制限制大载量任务顺序超出车容量，或时间窗口严重冲突），可能会导致求解出不合法的解（Infeasible Solution），或在校验解的可行性（check）时报错。因此，在配置 Relation 时需保证其物理逻辑的合理性。

### 示例

```python
problem = (
    Problem.empty()
    # 强制让车辆 vehicle_1 按先后顺序完成 pickup_1 和 delivery_1
    .add_relation_sequence(
        jobs=["pickup_1", "delivery_1"],
        vehicle_id="vehicle_1"
    )
)
```

## 2.1.1.5. Clustering

Clustering 用于把相近或相关 jobs 组合起来，减少不现实的 ETA 或提升路线结构质量。Python Interface 当前以兼容 pragmatic schema 为主，复杂 clustering 配置建议直接使用 raw JSON：

```python
problem_dict = problem.to_dict()
problem_dict["plan"]["clustering"] = {...}
problem = Problem.from_dict(problem_dict)
```

如果未来新增 clustering builder，应遵循 `Problem` builder 规则：链式返回、字段透传、native validation 为准。

## 2.1.1.6. Objectives

Objectives 描述了求解器的优化目标和约束惩罚项的优先级。在 Python Interface 中，可以通过 `Objective` 工厂类创建目标，并使用 `set_objectives_typed` 方法在 `Problem` 上进行配置。

### 优化目标配置方式

求解器支持**多级优先级（Hierarchical Objectives）**目标配置。通过嵌套列表指定，外层列表的每个元素代表一个优先级层级（按从前到后的顺序进行多目标优化）：

```python
from vrp_cli import Objective

problem = Problem.empty()

# 推荐：强类型多级目标配置
problem.set_objectives_typed([
    # 第一优先级：最优先减少未分配任务数，并尽量减少派车数
    [Objective.minimize_unassigned(), Objective.minimize_tours()],
    # 第二优先级：在此基础上，使总运营成本最低
    [Objective.minimize_cost()]
])
```

如果需要使用未被 Python SDK 直接封装的优化目标，或者需要使用原始结构，也可以直接传入原生字典列表：

```python
# 备选：直接设置原始字典结构
problem.set_objectives([
    [{"type": "minimize-unassigned"}, {"type": "minimize-tours"}],
    [{"type": "minimize-cost"}]
])
```

### 优化目标分类说明

支持的目标可以分为以下四类：

#### 1. 成本目标 (Cost Objectives)
用于控制路线的整体成本计算基准。一个问题**必须且只能配置其中一种**：
* `Objective.minimize_cost()`：最小化运营总成本（包含车辆固定的出车成本、行驶时间和距离成本的线性组合）。
* `Objective.minimize_distance()`：仅最小化车辆行驶总距离。
* `Objective.minimize_duration()`：仅最小化车辆行驶总时长。

#### 2. 数值目标 (Scalar Objectives)
针对解的全局特征进行优化的指标：
* `Objective.minimize_unassigned(breaks=None)`：最小化未分配任务数。参数 `breaks` (如 `0.5` 等) 可以微调未分配休息点的惩罚权重。
* `Objective.minimize_tours()`：尽量减少总出车数。
* `Objective.maximize_tours()`：在某些排班饱满度场景下，尽量增加总出车数。
* `Objective.minimize_arrival_time()`：优选服务时间靠前的解，使车辆尽快完成配送任务。

#### 3. 任务分配/分布目标 (Job Distribution Objectives)
微调任务在路线中排布的位置与形态：
* `Objective.maximize_value()`：最大化已拉运任务的经济价值（配合 `set_job_value` 使用）。

#### 4. 工作均衡目标 (Work Balance Objectives)
在多个出车路线之间均衡工作量（通常需要与 Cost 类目标置于同级 `multi-objective` 列表中，以进行联合估算）：
* `Objective.balance_max_load(threshold=None)`：均衡车辆的最大载重量。
* `Objective.balance_activities(threshold=None)`：均衡每辆车服务的任务数（服务量均衡）。
* `Objective.balance_distance(threshold=None)`：均衡每辆车的行驶距离。
* `Objective.balance_duration(threshold=None)`：均衡每辆车的总工作时间。
  * `threshold`：均衡灵敏度阈值系数，用于平滑较小的差异。

### 默认缺省目标行为 (Default Fallback)

如果你没有在 `Problem` 中显式调用 `set_objectives`，求解器将根据输入数据自动匹配以下默认的多目标优先级规则：

1. **常规默认行为**：
   ```json
   1级: minimize-unassigned  (最优先分配完所有任务)
   2级: minimize-tours       (在任务分配最多的前提下，车数越少越好)
   3级: minimize-cost        (最后使整体行驶成本最低)
   ```
2. **当任务包含 Value 时**：如果有任何任务调用了 `set_job_value` 且价值大于 0，则默认规则变为：
   ```json
   1级: maximize-value       (最优先拉运高经济价值的任务)
   2级: minimize-unassigned
   3级: minimize-tours
   4级: minimize-cost
   ```
3. **当任务包含 Order 时**：如果有任务配置了 Task order 顺序，则会在 `minimize-tours` 层级之后自动插入 `tour-order` 评估层级。

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

如果 Problem 中使用了多个不同的车型 profile（例如 `normal_car` 和 `normal_bike`），则需要使用 `MatrixCollection` 容器将各 profile 的矩阵打包：

```python
from vrp_cli import MatrixCollection

matrices = (
    MatrixCollection()
    .add(car_matrix)
    .add(bike_matrix)
)
solution = solve(problem, matrices=matrices.to_list(), config=config)
```

### Time-dependent matrix

如果两点之间的耗时与行驶距离随时间而变化（例如考虑早晚高峰拥堵），可以为同一 profile 提供不同时间戳（Timestamp）下的多张矩阵。`MatrixCollection` 提供了专门的 `add_time_dependent` 方法进行快捷配置：

```python
# 键为 RFC3339 格式的时间戳，值为该时间戳下对应的 durations 和 distances
timestamp_data = {
    "2019-07-04T08:00:00Z": {
        "durations": [0, 900, 900, 0],
        "distances": [0, 3840, 3840, 0],
    },
    "2019-07-04T12:00:00Z": {
        "durations": [0, 609, 609, 0],
        "distances": [0, 3840, 3840, 0],
    }
}

matrices = MatrixCollection()
matrices.add_time_dependent(profile="normal_car", timestamp_to_data=timestamp_data)
```

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
