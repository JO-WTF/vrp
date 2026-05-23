"""
Example showing how to extract location indices and use them.
This is useful when interfacing with external routing engines (OSRM, Valhalla)
to know exactly what matrix dimensions the solver expects.
"""

from vrp_cli import Problem, RoutingMatrix, solve

def run() -> None:
    # 1. Create a problem with coordinate-based locations
    problem = (
        Problem.empty()
        .add_vehicle(
            "vehicle_1",
            start_location=(52.5200, 13.4050), # Berlin
            start_earliest="2024-01-01T08:00:00Z",
            capacity=[10],
            costs={"distance": 1, "time": 1},
        )
        .add_delivery("job_1", (52.5166, 13.3833), demand=[5]) # Near Brandenburg Gate
        .add_delivery("job_2", (52.5300, 13.3900), demand=[5]) # Berlin Hbf
    )

    # 2. Extract locations. The order returned by get_locations() corresponds
    # to the exact flattened indices needed by the solver's MatrixCollection.
    locations = problem.get_locations()
    print("Solver requires a matrix for these locations in this specific order:")
    for idx, loc in enumerate(locations):
        print(f"Index {idx}: {loc}")
        
    num_locations = len(locations)
    print(f"\nExpected matrix size: {num_locations}x{num_locations} = {num_locations**2} elements")

    # 3. Simulate fetching a matrix from an external API (like OSRM)
    # based on the coordinates in `locations`.
    # For this example, we mock the matrix:
    travel_times = [
        0, 300, 600,
        300, 0, 400,
        600, 400, 0
    ]
    distances = [
        0, 2000, 4000,
        2000, 0, 3000,
        4000, 3000, 0
    ]

    matrices = [RoutingMatrix(profile="normal_car", durations=travel_times, distances=distances)]

    # 4. Validate the matrices against the problem dimensions!
    problem.validate_matrices(matrices)
    print("\nMatrix validation passed!")

if __name__ == "__main__":
    run()
