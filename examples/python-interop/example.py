import pragmatic_types as prg
from vrp_cli import Config, Problem, RoutingMatrix, solve

# if you want to use approximation, you can skip this definition and pass empty list later
# also there is a get_locations method to get list of locations in expected order.
# you can use this list to fetch routing matrix externally
matrix = RoutingMatrix(
    profile='normal_car',
    durations=[0, 609, 981, 906, 813, 0, 371, 590, 1055, 514, 0, 439, 948, 511, 463, 0],
    distances=[0, 3840, 5994, 5333, 4696, 0, 2154, 3226, 5763, 2674, 0, 2145, 5112, 2470, 2152, 0],
)


# specify termination criteria: max running time in seconds or max amount of refinement generations
config = Config(max_time=5, max_generations=1000)

# specify test problem
problem = Problem(prg.Problem(
    plan=prg.Plan(
        jobs=[
            prg.Job(
                id='delivery_job1',
                deliveries=[
                    prg.JobTask(
                        places=[
                            prg.JobPlace(
                                location=prg.Location(lat=52.52599, lng=13.45413),
                                duration=300,
                                times=[['2019-07-04T09:00:00Z', '2019-07-04T18:00:00Z']]
                            ),
                        ],
                        demand=[1]
                    )
                ]
            ),
            prg.Job(
                id='pickup_job2',
                pickups=[
                    prg.JobTask(
                        places=[
                            prg.JobPlace(
                                location=prg.Location(lat=52.5225, lng=13.4095),
                                duration=240,
                                times=[['2019-07-04T10:00:00Z', '2019-07-04T16:00:00Z']]
                            )
                        ],
                        demand=[1]
                    )
                ]
            ),
            prg.Job(
                id="pickup_delivery_job3",
                pickups=[
                    prg.JobTask(
                        places=[
                            prg.JobPlace(
                                location=prg.Location(lat=52.5225, lng=13.4095),
                                duration=300,
                                tag="p1"
                            )
                        ],
                        demand=[1]
                    )
                ],
                deliveries=[
                    prg.JobTask(
                        places=[
                            prg.JobPlace(
                                location=prg.Location(lat=52.5165, lng=13.3808),
                                duration=300,
                                tag="d1"
                            ),
                        ],
                        demand=[1]
                    )
                ]
            )
        ]
    ),
    fleet=prg.Fleet(
        vehicles=[
            prg.VehicleType(
                typeId='vehicle',
                vehicleIds=['vehicle_1'],
                profile=prg.VehicleProfile(matrix='normal_car'),
                costs=prg.VehicleCosts(fixed=22, distance=0.0002, time=0.005),
                shifts=[
                    prg.VehicleShift(
                        start=prg.VehicleShiftStart(
                            earliest="2019-07-04T09:00:00Z",
                            location=prg.Location(lat=52.5316, lng=13.3884),
                        ),
                        end=prg.VehicleShiftEnd(
                            latest="2019-07-04T18:00:00Z",
                            location=prg.Location(lat=52.5316, lng=13.3884),
                        )
                    )
                ],
                capacity=[10]
            )
        ],
        profiles=[prg.RoutingProfile(name='normal_car')]
    )

))

def on_iteration(generation, solution):
    statistic = solution.statistic
    print(
        "iteration callback:",
        f"generation={generation}",
        f"cost={statistic['cost']}",
        f"routes={len(solution.get('tours', []))}",
        f"unassigned={len(solution.get('unassigned', []))}",
    )


solution = solve(
    problem=problem,
    matrices=[matrix],
    config=config,
    on_iteration=on_iteration,
    every=100,
)

print(solution)
