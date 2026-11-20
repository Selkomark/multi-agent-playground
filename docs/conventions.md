# Repository Conventions

## Directory structure

- `experiments/` holds one directory per experiment. Directory names are lowercase kebab-case, prefixed with a zero-padded two-digit sequence number, for example `01-orchestrator-worker`.
- `docs/` at the root holds project-wide documentation only.
- Every experiment contains:
  - `README.md`: purpose, hypothesis, how to run, results summary, and a "Documentation" section linking to every file in its `docs/` directory.
  - `docs/`: experiment-specific documentation. At minimum a `design.md`. Add `findings.md` once there are results.
- An experiment may also contain `validations/`: short spikes that test an assumption before a build. It has a `README.md` listing every spike, and one numbered directory per spike (`01-<name>/`) with its own `README.md`. The experiment README links to `validations/README.md`.

## Documentation chain

Documentation is discoverable top-down:

1. Root `README.md` lists every experiment in the Experiments table with a link to `experiments/<name>/README.md`.
2. The experiment `README.md` links to every document in its `docs/` directory.
3. Documents in `docs/` may link to each other, but nothing outside the experiment should link directly into them. Go through the experiment README.

## Diagrams

Diagrams in any README or doc are Mermaid code blocks, never ASCII art. Directory trees in a plain code block are not diagrams and are fine.

The design rules live in the `mermaid-diagrams` skill (`.claude/skills/mermaid-diagrams/SKILL.md`). In short:

- `flowchart TD` (or `LR` for short linear flows), 6 to 12 nodes.
- 3 or 4 `classDef` styles with explicit text colors, so the diagram reads in both GitHub light and dark modes. Do not rely on the default theme.
- Labels in double quotes, 2-4 words per line, with shapes that carry meaning.
- Related nodes grouped in `subgraph` blocks with bold titles, and labeled conditional arrows.
- A two-sentence explanation directly below the diagram.

## Adding an experiment

Use the `experiment` skill (`/experiment new <name>`), or do it by hand:

1. Create `experiments/NN-<name>/` with `README.md` and `docs/design.md`.
2. Add a row to the Experiments table in the root `README.md`.
3. Make sure the experiment README's Documentation section links to each file under its `docs/`.
