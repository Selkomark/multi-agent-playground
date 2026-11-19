# H2H: Harness-to-Harness Orchestration

_Created 2026-11-19_

**Status: design only.** This experiment currently holds documentation. Nothing is built, and the design is expected to change before any build is planned.

## Purpose

Find out whether complete agent harnesses (Claude Code, Copilot, Gemini and others) can work as a team, where each harness owns a domain of responsibility and reports status, instead of acting as a worker that answers one task and forgets.

A harness is a full agent product: a model plus its own loop, tools, permissions and ability to spawn sub-agents. Experiment 01 orchestrates small agents defined in one framework. H2H orchestrates whole harnesses that are opaque to each other.

The motivating case: one harness builds a UI, another tests it because it is better at UI testing, and a third owns customer service end to end, from development to support. A human sees the status of each side by side and approves or rejects their work.

## Hypothesis

A team of harnesses that own domains will handle multi-part projects better than a central orchestrator directing every step, because:

- Each owner keeps the context, tools and access for its domain, so no single orchestrator has to hold the detail of everything.
- Work is checked by someone who did not produce it: another harness, a script or a human.
- Harnesses are interchangeable behind a common protocol, so a harness with a different strength or budget can join later without changing the rest.

We expect the cost to be coordination overhead. H2H should lose to a single agent on small tasks, and the experiment should show where that line is.

## Setup

Not built yet. The intended shape:

- **Protocol:** A2A between harnesses, with each harness behind a wrapper that exposes it as an A2A service.
- **Core:** a ticket system with approval rules and budgets, enforced in code.
- **Team:** a pool of harnesses, each assigned a domain, optionally with one harness acting as coordinator.
- **Human:** approves, rejects with a reason, and unblocks decisions through the ticket system.
- **Configuration:** declared as code, with a CLI and a UI as views onto it.

## Running

Nothing to run yet.

## Results

None yet. Details go in `docs/findings.md` once there are results.

## Documentation

Read in this order:

- [docs/design.md](docs/design.md): architecture, roles and the communication model
- [docs/governance.md](docs/governance.md): tickets, proof of work, approvals, autonomy and intended use
- [docs/configuration.md](docs/configuration.md): config as code, the CLI and the UI
- [docs/authentication.md](docs/authentication.md): the four authentication problems and how to approach each
- [docs/roadmap.md](docs/roadmap.md): build stages and open questions
