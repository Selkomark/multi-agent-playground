# Repository Conventions

## Directory structure

- `experiments/` holds one directory per experiment. Directory names are lowercase kebab-case, prefixed with a zero-padded two-digit sequence number, for example `01-orchestrator-worker`.
- `docs/` at the root holds project-wide documentation only.
- Every experiment contains:
  - `README.md`: purpose, hypothesis, how to run, results summary, and a "Documentation" section linking to every file in its `docs/` directory.
  - `docs/`: experiment-specific documentation. At minimum a `design.md`. Add `findings.md` once there are results.

## Documentation chain

Documentation is discoverable top-down:

1. Root `README.md` lists every experiment in the Experiments table with a link to `experiments/<name>/README.md`.
2. The experiment `README.md` links to every document in its `docs/` directory.
3. Documents in `docs/` may link to each other, but nothing outside the experiment should link directly into them. Go through the experiment README.

## Adding an experiment

Use the `experiment` skill (`/experiment new <name>`), or do it by hand:

1. Create `experiments/NN-<name>/` with `README.md` and `docs/design.md`.
2. Add a row to the Experiments table in the root `README.md`.
3. Make sure the experiment README's Documentation section links to each file under its `docs/`.
