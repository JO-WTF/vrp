from vrp_cli import Config, Problem, Recreate, RoutingMatrix, solve


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
        (52.5225, 13.4095),
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

matrix = RoutingMatrix(
    profile="normal_car",
    durations=[0, 609, 981, 813, 0, 371, 1055, 514, 0],
    distances=[0, 3840, 5994, 4696, 0, 2154, 5763, 2674, 0],
)

config = (
    Config(max_time=5, max_generations=1000)
    .set_initial(
        Recreate.cheapest(),
        alternatives=[Recreate.farthest(), Recreate.regret(2, 3)],
    )
    .set_population_rosomaxa(selection_size=8)
)

solution = solve(problem, matrices=[matrix], config=config)
print(solution.statistic)
