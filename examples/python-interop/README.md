# Python interop

This folder contains a small Python facade over the `vrp_cli` Python binding.
It keeps the pragmatic JSON format available while providing Python-friendly
objects and helper builders.

## JSON assets

The interface is organized around the JSON assets used by pragmatic solving:

- `Problem` maps to `problem.json`.
- `RoutingMatrix` maps to one routing matrix JSON. Multiple matrices can be passed to `solve`.
- `Config` maps to solver `config.json`.
- `InitialSolution` maps to an optional pragmatic solution used as a starting point.
- `Solution` maps to solver output.
- `RoutingLocations` maps to the ordered location list used to request matrices from external routing services.

Each asset supports JSON-style construction:

```python
from vrp import Config, Problem, RoutingMatrix

problem = Problem.from_json("../../examples/data/pragmatic/simple.basic.problem.json")
matrix = RoutingMatrix.from_json("../../examples/data/pragmatic/simple.basic.matrix.json")
config = Config.from_json("../../examples/data/config/config.full.json")
```

and direct serialization:

```python
data = problem.to_dict()
text = problem.to_json(indent=2)
problem.write_json("problem.json", indent=2)
```

## Solving

```python
from vrp import Config, Problem, RoutingMatrix, solve

problem = Problem.from_json("../../examples/data/pragmatic/simple.basic.problem.json")
matrix = RoutingMatrix.from_json("../../examples/data/pragmatic/simple.basic.matrix.json")
config = Config(max_time=5, max_generations=1000)

solution = solve(problem, matrices=[matrix], config=config)
print(solution.statistic)
```

Use `on_iteration` to receive intermediate solutions:

```python
def on_iteration(generation, solution):
    print(generation, solution.statistic.get("cost"))

solution = solve(problem, matrices=[matrix], config=config, on_iteration=on_iteration, every=100)
```

## Building a problem

For common cases, start from `Problem.empty()`:

```python
from vrp import Problem

problem = (
    Problem.empty()
    .add_delivery("delivery_1", (52.52599, 13.45413), [1], duration=300)
    .add_vehicle(
        "vehicle_1",
        start_location=(52.5316, 13.3884),
        start_earliest="2019-07-04T09:00:00Z",
        end_latest="2019-07-04T18:00:00Z",
        capacity=[10],
    )
)
```

The builder intentionally covers common flows only. For advanced pragmatic
fields, pass raw dictionaries or load existing JSON with `Problem.from_json`.

## Routing matrices

The Python API uses `durations` because that is the natural domain term:

```python
from vrp import RoutingMatrix

matrix = RoutingMatrix(
    profile="normal_car",
    durations=[0, 609, 609, 0],
    distances=[0, 3840, 3840, 0],
)
```

When serialized, this becomes the pragmatic JSON field `travelTimes` expected by
the Rust solver:

```json
{
  "profile": "normal_car",
  "travelTimes": [0, 609, 609, 0],
  "distances": [0, 3840, 3840, 0]
}
```

## Config helpers

Simple config:

```python
from vrp import Config

config = Config(max_time=5, max_generations=1000)
```

Evolution helpers:

```python
from vrp import Config, Recreate

config = (
    Config.defaults(max_time=60, max_generations=5000)
    .set_initial(
        Recreate.cheapest(),
        alternatives=[Recreate.farthest(), Recreate.regret(2, 3)],
    )
    .set_population_rosomaxa(selection_size=8)
)
```

Hyper heuristic helpers:

```python
from vrp import Config, Hyper, LocalOperator, Probability, Recreate, Ruin, min_max, noise

config = Config.defaults().set_hyper_static(
    [
        Hyper.local_search(
            probability=Probability.scalar(0.05),
            times=min_max(1, 2),
            operators=[
                LocalOperator.swap_star(weight=200),
                LocalOperator.inter_route_best(weight=100, noise=noise(0.1, -0.1, 0.1)),
            ],
        ),
        Hyper.ruin_recreate(
            probability=Probability.scalar(1),
            ruins=[Ruin.group([Ruin.neighbour(1, 8, 16)], weight=10)],
            recreates=[Recreate.cheapest(weight=20), Recreate.skip_best(1, 2, weight=10)],
        ),
    ]
)
```

All helpers produce plain dictionaries, so they can be mixed with raw config JSON.

## Examples

- `basic.py` builds a small problem using the Python builders.
- `json_assets.py` loads problem, matrix, and config JSON from `examples/data`.
- `callback.py` shows iteration callbacks.
- `initial_solution.py` shows how to pass an initial solution asset.
- `hyper_config.py` prints a composed hyper heuristic config.

## Tests

Run facade tests without building the native extension:

```bash
python -m unittest discover examples/python-interop/tests
```

These tests validate Python-side serialization and binding dispatch. To validate
the Rust/PyO3 binding itself, run the Rust checks with the Python binding feature
enabled:

```bash
cargo fmt --check
cargo check --features py_bindings
```
