"""
Example of configuring and solving a time-dependent routing problem.
"""

from vrp_cli import Problem, RoutingMatrix, Config, solve

def run() -> None:
    # 1. Create a basic problem with a vehicle and a couple of jobs
    problem = (
        Problem.empty()
        .add_vehicle(
            "vehicle_1",
            start_location=(0, 0),
            profile="car",
            start_earliest="2024-01-01T08:00:00Z",
            start_latest="2024-01-01T09:00:00Z",
            capacity=[10],
            costs={"distance": 1, "time": 1},
        )
        .add_delivery("job_1", (1, 0), demand=[5])
        .add_delivery("job_2", (2, 0), demand=[5])
    )

    # 2. Extract the auto-generated locations (0,0), (1,0), (2,0)
    # They are assigned internal IDs: 0, 1, 2
    # So we need a 3x3 matrix.
    
    # Let's say during normal hours, travel times are standard:
    normal_times = [
        0, 10, 20,
        10, 0, 10,
        20, 10, 0
    ]
    distances = [
        0, 10, 20,
        10, 0, 10,
        20, 10, 0
    ]
    
    # But during rush hour (e.g. 08:30 to 09:30), travel times are doubled:
    rush_hour_times = [
        0, 20, 40,
        20, 0, 20,
        40, 20, 0
    ]

    # 3. Create RoutingMatrix instances
    # Note: timestamps must be provided in an ISO string for timestamp-based evaluation
    # Time-aware routing requires all matrices to have a timestamp.
    base_ts = "2024-01-01T00:00:00Z"
    rush_hour_ts = "2024-01-01T08:30:00Z"
    
    matrices = [
        RoutingMatrix(profile="car", timestamp=base_ts, durations=normal_times, distances=distances),
        RoutingMatrix(profile="car", timestamp=rush_hour_ts, durations=rush_hour_times, distances=distances)
    ]

    # 4. Solve the problem passing the matrices
    solution = solve(problem, matrices=matrices, config=Config.fast())

    # 5. Inspect the resulting route
    print(f"Total time spent: {solution.statistic.get('duration', 0)}")
    
    for tour in solution.tours:
        for stop in tour.stops:
            print(f"Stop at {stop.location} arriving at {stop.time.arrival} and departing at {stop.time.departure}")

if __name__ == "__main__":
    run()
