# Multi-Agent Playground

A sandbox for running experiments in multi-agent development. Each experiment lives in its own directory under `experiments/` and is self-contained: code, a README, and its own `docs/` folder.

## Layout

```
.
├── README.md          # this file: index of all experiments
├── docs/              # project-wide documentation (conventions, shared notes)
└── experiments/       # one directory per experiment
    └── <name>/
        ├── README.md  # what the experiment is, how to run it, links into docs/
        └── docs/      # experiment-specific documentation
```

Conventions are documented in [docs/conventions.md](docs/conventions.md) and enforced by the `experiment` skill in `.claude/skills/`.

## Experiments

| # | Experiment | Summary |
|---|------------|---------|
| 01 | [Domain Name Research](experiments/01-domain-name-research/README.md) | Agents propose domain names for a business idea, check availability and price per provider, and rank them by price |
| 02 | [H2H: Harness-to-Harness Orchestration](experiments/02-h2h/README.md) | Design for harnesses working as a team of domain owners, coordinated through tickets and human approval (documentation only) |
