"""
Example of solving a problem with multiple vehicle profiles (e.g., car vs bike)
and providing distinct routing matrices for each profile.
"""

from vrp_cli import Problem, RoutingMatrix, Config, solve

def run() -> None:
    # 1. Create a problem with multiple vehicle profiles
    problem = (
        Problem.empty()
        # A fast vehicle with a "car" profile
        .add_vehicle(
            "car_1",
            type_id="car_type",
            start_location=(0, 0),
            profile="car",
            start_earliest="2024-01-01T08:00:00Z",
            capacity=[10],
            costs={"distance": 1, "time": 1},
        )
        # A slow vehicle with a "bike" profile
        .add_vehicle(
            "bike_1",
            type_id="bike_type",
            start_location=(0, 0),
            profile="bike",
            start_earliest="2024-01-01T08:00:00Z",
            capacity=[5],
            costs={"distance": 1, "time": 2}, # Time is more expensive or bike is just slower
        )
        .add_delivery("job_1", (1, 0), demand=[5])
        .add_delivery("job_2", (2, 0), demand=[5])
    )

    # 2. Add multiple matrices
    matrices = [
        # Fast travel times for car
        RoutingMatrix(
            profile="car",
            durations=[
                0, 10, 20,
                10, 0, 10,
                20, 10, 0
            ],
            distances=[
                0, 10, 20,
                10, 0, 10,
                20, 10, 0
            ]
        ),
        # Slower travel times for bike
        RoutingMatrix(
            profile="bike",
            durations=[
                0, 30, 60,
                30, 0, 30,
                60, 30, 0
            ],
            distances=[
                0, 10, 20,
                10, 0, 10,
                20, 10, 0
            ]
        )
    ]

    # 3. Solve the problem
    solution = solve(problem, matrices=matrices, config=Config.fast())

    # 4. Inspect the resulting route
    print(f"Total cost: {solution.total_cost}")
    
    for tour in solution.tours:
        print(f"\nTour for {tour.vehicle_id} (Type: {tour.type_id}):")
        print(f"  Distance: {tour.distance}, Duration: {tour.duration}")
        for stop in tour.stops:
            print(f"  - Stop at {stop.location}")

if __name__ == "__main__":
    run()
