# Configuration: H2H

How a team is defined and changed.

## Principle

The team is declared as code, in the way Terraform declares infrastructure. The code is the single source of truth. The CLI and the UI are views onto it and both go through one API over one schema. If the UI kept its own settings, the two would drift and nobody would know which was in force.

## Why config as code

- **Reviewable.** The rules that limit a harness live in version control, with a history of who changed what and why.
- **Reproducible.** The same files set up the same team on another project or machine.
- **Improvable.** Lessons from rejections become config changes. A harness can propose a change to the rules as a pull request, which keeps a human gate on the rules themselves.

## Config and state

Declared config and runtime state are kept apart. A config file that fills up with status becomes unreviewable.

| Declared in config | Runtime state, not in config |
|---|---|
| The harness pool: how to start each harness, and which one owns which domain | Tickets and their status |
| Permissions and credentials each owner may use, by reference | Proof attached to tickets |
| Budgets | Approvals and rejections |
| Approval rules by ticket type | Session history |
| What counts as proof for each kind of work | |
| Round limits and other guardrails | Running sessions, their workspaces and logs |
| The paths each domain owns | Usage per ticket: model, effort, tokens, rounds, outcome |
| Model and effort per domain and per phase of work | Estimates and actuals |
| Planning mode: kanban, or managed with a project manager | Sprints and retro reports |
| Sprint budgets | |

Secrets are never in the config. The config names a secret, and the value lives in a secret store or the environment.

## Plan and apply

A config change does not take effect directly. A plan step shows the difference first, for example "this gives the support owner write access to the deploy pipeline". Permission changes are the riskiest edits in the system, and the preview is cheap protection.

## Interfaces

| Interface | Audience | Best at |
|---|---|---|
| Config files | Anyone who wants the setup versioned and improving over time | Defining the team and its rules |
| CLI | Technical users, scripts, and harnesses themselves | Plan, apply, listing sessions, following logs, attaching to a session |
| UI, started with `h2h serve --port <n>` | Everyone, especially for approvals | The ticket board, the proof viewer, the side-by-side status view, a terminal for each session |

H2H is one binary. The CLI is the primary interface, and the UI is the same binary serving a web page, so there is nothing extra to install. The commands are listed in [runtime.md](runtime.md).

The UI matters most for the human approval side. It earns its place there before it does for editing config.

## Build order

1. **Schema.** The config format is the real design work and everything else depends on it.
2. **CLI.** Small to build and scriptable.
3. **UI.** The largest effort.

The config schema itself is not designed yet. See [roadmap.md](roadmap.md).
