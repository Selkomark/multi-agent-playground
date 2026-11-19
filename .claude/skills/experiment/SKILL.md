---
name: experiment
description: Repository conventions for the multi-agent-playground. Use when creating a new experiment, adding documentation to an experiment, or checking that the repo layout and README index are consistent. Invoke with "new <name>" to scaffold an experiment or "check" to audit the structure.
---

# Experiment Structure

This repo is a sandbox for multi-agent development experiments. Follow these rules whenever you create or modify anything under `experiments/`, `docs/`, or the root `README.md`.

## Layout

```
README.md                      # root index: Experiments table, one row per experiment
docs/                          # project-wide docs only (conventions, shared notes)
experiments/
└── NN-<kebab-name>/           # NN = zero-padded sequence number (01, 02, ...)
    ├── README.md              # purpose, hypothesis, how to run, results, Documentation section
    └── docs/
        ├── design.md          # required: architecture and approach
        └── findings.md        # add once there are results
```

## Rules

1. **Every experiment has a README.md and a docs/ directory.** No exceptions, even for throwaway experiments.
2. **The root README.md Experiments table lists every experiment**, linking to `experiments/NN-<name>/README.md`. Keep rows in sequence order. Remove the `_none yet_` placeholder row when adding the first experiment.
3. **The experiment README has a `## Documentation` section** that links to every file in its `docs/`. When you add a doc, add the link.
4. **Experiment-specific docs never go in the root `docs/`.** Only project-wide material lives there.
5. **Links flow downward**: root README -> experiment README -> experiment docs. Do not link from the root README directly into an experiment's `docs/`.
6. **Naming**: lowercase kebab-case, numeric prefix. Pick the next unused number by listing `experiments/`.

## Commands

### `new <name>`

Scaffold a new experiment:

1. Determine the next sequence number `NN` from existing directories in `experiments/`.
2. Create `experiments/NN-<name>/` by copying the templates in `templates/` from this skill directory (`README.md`, `docs/design.md`). Fill in the placeholders `{{TITLE}}`, `{{NAME}}`, `{{DATE}}`.
3. Add a row to the Experiments table in the root `README.md`: `| NN | [Title](experiments/NN-<name>/README.md) | one-line summary |`.
4. Report the created paths.

### `check`

Audit the repo and report violations:

- Every directory in `experiments/` has `README.md` and `docs/` with at least `design.md`.
- Every experiment appears in the root README table, and every table row points at an existing experiment.
- Every file in each experiment's `docs/` is linked from that experiment's README Documentation section.

Fix violations when asked; otherwise just report them.

## Extending these conventions

When the user introduces a new structural rule (a new required file, a new directory, a new naming scheme), update this SKILL.md, the templates in `templates/`, and `docs/conventions.md` so all three stay in agreement.
