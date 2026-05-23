"""
Example of building a complex Config and exporting/importing it.
"""

from vrp_cli import Config, Recreate, Ruin, LocalOperator, Probability

def run() -> None:
    # 1. Create a complex config programmatically
    config = (
        Config.defaults(max_time=120, max_generations=5000)
        .set_parallelism((4, 2))
        .set_experimental(True)
        .set_progress(log_best=100)
        .include_geojson()
        .set_population_rosomaxa(selection_size=4, exploration_ratio=0.8)
        .set_initial(
            method=Recreate.cheapest(weight=1),
            alternatives=[
                Recreate.farthest(weight=2),
                Recreate.blinks(weight=1)
            ],
            max_size=8,
            quota=0.1
        )
        .set_hyper_static([
            LocalOperator.swap_star(weight=5),
            LocalOperator.inter_route_best(weight=2),
            Ruin.adjusted_string(probability=0.5, lmax=10, cavg=5, alpha=0.1)
        ])
    )

    # 2. Export Config to JSON file
    config_file = "complex_config.json"
    config.write_json(config_file)
    print(f"Config successfully exported to {config_file}")

    # 3. Load Config from JSON file
    loaded_config = Config.from_json(config_file)
    print(f"Loaded config max generations: {loaded_config.to_dict()['termination']['maxGenerations']}")
    print(f"Loaded config uses rosomaxa: {loaded_config.to_dict()['evolution']['population']['type'] == 'rosomaxa'}")

    import os
    if os.path.exists(config_file):
        os.remove(config_file)

if __name__ == "__main__":
    run()
