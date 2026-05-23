"""
Example of configuring driver breaks and job reloads during a route.
"""

from vrp_cli import Problem, Config, solve

def run() -> None:
    # 1. Create a problem with breaks and reloads
    problem = (
        Problem.empty()
        .add_vehicle(
            "vehicle_1",
            start_location=(0, 0),
            end_location=(0, 0),
            start_earliest="2024-01-01T08:00:00Z",
            start_latest="2024-01-01T09:00:00Z",
            capacity=[10],
            costs={"distance": 1, "time": 1},
            # Add a break during the shift
            breaks=[
                {
                    "time": {
                        "earliest": "2024-01-01T12:00:00Z",
                        "latest": "2024-01-01T14:00:00Z"
                    },
                    "duration": 3600,  # 1 hour break
                    "locations": [(5, 5)]  # Optional: break location
                }
            ],
            # Add reload stations to restock vehicle capacity
            reloads=[
                {
                    "location": (0, 0),
                    "duration": 1800, # 30 min to reload
                    "tag": "depot_reload"
                }
            ]
        )
        # Add normal delivery jobs
        .add_delivery("job_1", (2, 2), demand=[5])
        .add_delivery("job_2", (8, 8), demand=[6])
        .add_delivery("job_3", (4, 4), demand=[5])
    )

    # 2. Configure solving parameters
    config = Config.fast()

    # 3. Solve the problem
    solution = solve(problem, config=config)

    # 4. Inspect the resulting route
    print(f"Total cost: {solution.total_cost}")
    
    for tour in solution.tours:
        print(f"\nTour for {tour.vehicle_id}:")
        for stop in tour.stops:
            loc = stop.location
            activities = [a.type for a in stop.activities]
            print(f" - Stop at {loc} doing {activities}")
            if "break" in activities:
                print("   [!] Driver took a break here")
            if "reload" in activities:
                print("   [!] Vehicle reloaded capacity here")

if __name__ == "__main__":
    run()
