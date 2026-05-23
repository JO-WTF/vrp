from vrp import Config, Hyper, LocalOperator, Probability, Recreate, Ruin, min_max, noise


config = Config.defaults(max_time=60, max_generations=5000).set_hyper_static(
    [
        Hyper.local_search(
            probability=Probability.scalar(0.05),
            times=min_max(1, 2),
            operators=[
                LocalOperator.swap_star(weight=200),
                LocalOperator.inter_route_best(weight=100, noise=noise(0.1, -0.1, 0.1)),
                LocalOperator.sequence(weight=100),
            ],
        ),
        Hyper.ruin_recreate(
            probability=Probability.scalar(1),
            ruins=[
                Ruin.group(
                    [
                        Ruin.neighbour(1, 8, 16),
                        Ruin.worst_job(1, 8, 16, skip=4),
                    ],
                    weight=10,
                )
            ],
            recreates=[
                Recreate.cheapest(weight=20),
                Recreate.regret(2, 3, weight=20),
                Recreate.skip_best(1, 2, weight=10),
            ],
        ),
    ]
)

print(config.to_json(indent=2))
