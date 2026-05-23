# VRP Visualizer (`vrp-vis`)

`vrp-vis` is an interactive visualization tool for the Vehicle Routing Problem (VRP) solver. It allows you to visually inspect the search trajectory, convergence metrics, and the geographical routes of your VRP solutions.

## Architecture

The tool is split into two main components:
1. **Python CLI (`vrp-vis`)**: Wraps the Python bindings of the `vrp-cli` solver, tracks the generation of new best solutions during optimization, and writes the trajectory data into a local `.vrp_vis_data` directory. It also provides a local HTTP server to serve the frontend.
2. **Frontend Dashboard**: A Vue 3 + ECharts single-page application that reads the generated JSON data and renders the interactive map and convergence chart.

## Getting Started

### 1. Solving a Problem with Tracking Enabled

You can run the solver with visualization tracking enabled using the `solve` command. This will execute the VRP solver and automatically record snapshots whenever a new best solution is found.

```bash
uv run vrp-vis solve <path_to_problem.json> [OPTIONS]
```

**Available Options:**
- `--matrices <path...>`: One or more routing matrix JSON files.
- `--config <path>`: Path to a solver configuration JSON file.
- `--name <string>`: A custom name for this run (defaults to the problem filename).
- `--max-time <seconds>`: Maximum running time (used if no config is provided). Default is 60s.
- `--max-gen <integer>`: Maximum number of generations (used if no config is provided). Default is 3000.

**Example:**
```bash
uv run vrp-vis solve ./examples/data/pragmatic/basics/multi-day.basic.problem.json --max-time 100 --max-gen 1000000
```
Upon completion, the tracking data will be saved to `.vrp_vis_data/<run_name>.json`.

### 2. Viewing the Dashboard

To view the interactive dashboard, start the built-in HTTP server:

```bash
uv run vrp-vis serve --port 8080
```

Then, open your web browser and navigate to `http://localhost:8080`. 

From the dashboard, you can:
- **Select a Run**: Choose any previously solved problem from the top dropdown menu.
- **Playback the Timeline**: Use the slider or the Previous/Next buttons to step through the solver's generations and watch how the routes evolved.
- **Inspect Routes**: Hover over the stops or route lines on the map to view detailed metrics such as arrival/departure times, distance, load, and actual vs. planned service durations.
- **Analyze Convergence**: View the cost reduction over time on the bottom right convergence chart.

## Development

If you wish to modify the frontend dashboard:

1. Navigate to the frontend directory:
   ```bash
   cd vrp-cli/python/vrp_cli/vis/frontend
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Start the Vite dev server:
   ```bash
   npm run dev
   ```
4. Once you have finished your changes, build the production bundle (the Python `serve` command serves these static files):
   ```bash
   npm run build
   ```
