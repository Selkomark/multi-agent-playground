# H2H: Harness-to-Harness Orchestration

_Created 2026-11-19_

**Status: design, with validation in progress.** The design is documented and nothing is built. Short spikes under [`validations/`](validations/README.md) test the riskiest assumptions before a build is planned.

## Purpose

Find out whether complete agent harnesses (Claude Code, Copilot, Codex and others) can work as a team, where each harness owns a domain of responsibility and reports status, instead of acting as a worker that answers one task and forgets.

A harness is a full agent product: a model plus its own loop, tools, permissions and ability to spawn sub-agents. Experiment 01 orchestrates small agents defined in one framework. H2H orchestrates whole harnesses that are opaque to each other.

The motivating case: one harness builds a UI, another tests it because it is better at UI testing, and a third owns customer service end to end, from development to support. A human sees the status of each side by side and approves or rejects their work.

## Hypothesis

A team of harnesses that own domains will handle multi-part projects better than a central orchestrator directing every step, because:

- Each owner keeps the context, tools and access for its domain, so no single orchestrator has to hold the detail of everything.
- Work is checked by someone who did not produce it: another harness, a script or a human.
- Harnesses are interchangeable behind a common protocol, so a harness with a different strength or budget can join later without changing the rest.

We expect the cost to be coordination overhead. H2H should lose to a single agent on small tasks, and the experiment should show where that line is.

Similar tools already exist and are known to be expensive to run. H2H only earns its place if its design keeps that cost down; see [docs/cost.md](docs/cost.md) and [docs/prior-art.md](docs/prior-art.md).

## Setup

Not built yet. The intended shape:

- **Tool:** a single `h2h` binary, written in Go. It is a CLI first, and `h2h serve --port <n>` adds a web UI.
- **Sessions:** each harness runs in its own terminal session and workspace under a small keeper process, so sessions survive a crash of H2H and can be rejoined.
- **Visibility:** the user can list active harnesses, follow their logs, and jump into any session's terminal.
- **Reporting:** harnesses report status and proof through a tool H2H provides. A2A is kept for harnesses on other machines.
- **Core:** a ticket system with approval rules and budgets, enforced in code.
- **Team:** a pool of harnesses, one owner per domain, optionally with one harness acting as coordinator.
- **Planning:** kanban by default. An optional project manager adds estimation, sprints bounded by budget, and a retro.
- **Cost:** coordination is done by code first, small agents second and a harness last.
- **Permissions:** rules declared in config answer a harness's permission requests on the user's behalf. Anything not covered goes to the user.
- **Human:** approves, rejects with a reason, and unblocks decisions through the ticket system.
- **Configuration:** declared as code, with the CLI and the UI as views onto it.

## Running

Nothing of H2H itself to run yet. The validation spikes have their own instructions in [validations/README.md](validations/README.md).

## Results

None yet. Details go in `docs/findings.md` once there are results.

## Documentation

Read in this order:

- [docs/design.md](docs/design.md): architecture, roles and the communication model
- [docs/runtime.md](docs/runtime.md): sessions, keepers, monitoring, jumping in, crash recovery and the choice of Go
- [docs/governance.md](docs/governance.md): tickets, proof of work, approvals, autonomy, rework prevention and intended use
- [docs/planning.md](docs/planning.md): kanban and managed modes, the project manager, estimation, sprints and the retro
- [docs/cost.md](docs/cost.md): where cost comes from and how the design limits it
- [docs/permissions.md](docs/permissions.md): how H2H answers a harness's permission requests on the user's behalf
- [docs/configuration.md](docs/configuration.md): config as code, the CLI and the UI
- [docs/authentication.md](docs/authentication.md): the four authentication problems and how to approach each
- [docs/prior-art.md](docs/prior-art.md): existing projects and where H2H intends to differ
- [docs/risks.md](docs/risks.md): gaps found in the design review, with proposed directions
- [docs/roadmap.md](docs/roadmap.md): build stages and open questions

Validation spikes:

- [validations/README.md](validations/README.md): the assumptions being tested, how to run each spike, and results
