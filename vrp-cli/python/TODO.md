# Python Interface TODO

Track pragmatic Python interface coverage here. Check an item only when the
Python facade has a documented API and at least one test or example covering it.

## Core Assets

- [x] `Problem` JSON asset: `from_json`, `from_dict`, `to_dict`, `to_json`, `write_json`
- [x] `RoutingMatrix` JSON asset with Python `durations` API and pragmatic `travelTimes` serialization
- [x] `Config` JSON asset: raw JSON passthrough plus common builder helpers
- [x] `InitialSolution` JSON asset
- [x] `Solution` JSON asset with `statistic` and `tours` accessors
- [x] `RoutingLocations` JSON asset

## Solver Entry Points

- [x] `solve(problem, matrices, config)`
- [x] `solve(..., on_iteration=..., every=...)`
- [x] `solve(..., initial_solution=...)`
- [x] `solve(..., initial_solution=..., on_iteration=...)`
- [x] `validate(problem, matrices)`
- [x] `get_locations(problem)`
- [x] Convert other supported formats to pragmatic through Python facade
- [x] Expose solution feasibility/checker API
- [x] Expose geojson output as a first-class Python object/helper

## Problem Builder

- [x] Empty problem builder: `Problem.empty()`
- [x] Delivery job helper
- [x] Pickup job helper
- [x] Pickup-delivery job helper
- [x] Vehicle helper with basic shift, capacity, profile, costs
- [x] Profile helper
- [x] Raw relation helper
- [x] Raw objectives setter
- [x] Service job helper
- [x] Multi-place task helper
- [x] Job skills helper
- [x] Job priority helper
- [x] Job value helper
- [x] Job group/compatibility helpers
- [x] Job order/sequence constraints helper
- [x] Relation typed helpers for all pragmatic relation types
- [x] Objective typed helpers for all pragmatic objective types
- [x] Vehicle multi-shift helper
- [x] Vehicle break helper
- [x] Vehicle reload helper
- [x] Vehicle recharge helper
- [x] Vehicle resource helper
- [x] Vehicle dispatch/open route helper
- [x] Vehicle limits helper
- [x] Vehicle skills helper
- [x] Fleet profile speed/scale helper
- [x] Location index helper
- [x] Multi-dimensional capacity/demand validation
- [x] Problem-level validation helpers before calling native binding

## Routing Matrix

- [x] Single matrix asset
- [x] Multiple matrices passed to `solve`
- [x] Optional `timestamp` field for time-dependent matrices
- [x] Matrix collection helper
- [x] Matrix profile consistency validation against `fleet.profiles`
- [x] Matrix dimension validation against routing locations
- [x] Time-dependent matrix helper for multiple timestamps per profile
- [ ] Location list to external routing service workflow helper
- [x] Matrix construction from 2D duration/distance arrays

## Config

- [x] Termination helper: `maxTime`, `maxGenerations`
- [x] Variation/min-CV helper
- [x] Environment parallelism helper
- [x] Environment logging helper
- [x] Experimental flag helper
- [x] Telemetry progress helper
- [x] Telemetry metrics helper
- [x] Output `includeGeojson` helper
- [x] Evolution initial helper
- [x] Recreate method helpers
- [x] Population helpers: greedy, elitism, rosomaxa
- [x] Hyper helpers: dynamic/static selective
- [x] Hyper operator helper: decomposition
- [x] Hyper operator helper: local search
- [x] Hyper operator helper: ruin recreate
- [x] Local operator helpers
- [x] Ruin method helpers
- [x] Probability helpers
- [x] Config presets for common solve modes
- [x] Full typed model for `evolution.initial.alternatives`
- [x] Full typed model for `hyper.static-selective.operators`
- [x] Parameter validation for recreate/population/hyper helpers
- [x] Config merge/overlay helper
- [x] Config export/import examples for full config

## Solution And Initial Solution

- [x] Read/write solution JSON asset
- [x] Pass initial solution JSON to native binding
- [x] Strong typed solution model
- [x] Route/tour accessor helpers
- [x] Stop/activity accessor helpers
- [x] Unassigned jobs accessor helpers
- [x] Initial solution route builder
- [x] Initial solution unassigned helper
- [x] Solution to geojson helper
- [x] Solution summary/statistics helper

## Examples

- [x] Basic builder example
- [x] JSON assets example
- [x] Callback example
- [x] Initial solution example
- [x] Hyper config example
- [x] README usage guide
- [x] Objectives example
- [x] Relations example
- [x] Break/reload/recharge example
- [x] Time-dependent matrix example
- [x] Location index example
- [x] Multi-profile matrix example
- [x] Solution inspection example

## Tests

- [x] Routing matrix `durations` serialization test
- [x] Config builder serialization test
- [x] Problem builder serialization test
- [x] Initial solution binding dispatch test
- [x] Evolution helper serialization test
- [x] Hyper helper serialization test
- [x] Objective helper tests
- [x] Relation helper tests
- [x] Vehicle advanced helper tests
- [x] Routing matrix validation tests
- [x] Initial solution builder tests
- [x] Native `vrp_cli` integration tests

## Packaging

- [x] Decide final Python package layout
- [x] Move facade out of `examples` when package layout is decided
- [x] Add build instructions for PyO3/maturin or project-specific flow
- [x] Add API reference docs
- [x] Add CI step for Python facade tests
- [x] Add CI step for `cargo check --features py_bindings`
