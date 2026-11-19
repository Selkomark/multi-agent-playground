# Roadmap: H2H

Nothing here is scheduled. This is the order the design suggests, and the questions that must be answered before planning a build.

## Stages

Each stage gives a baseline for judging the next.

| Stage | What is built | What it tells us |
|---|---|---|
| 1. One harness behind A2A | A wrapper around one harness, called from an orchestrator, on a task that needs a harness (change code in a repo and run the tests). Compared with a plain agent that has file and shell tools | What a harness adds, and what the boundary costs |
| 2. Build and test loop | Two instances of the same harness as builder and tester, with the commit handoff, a test environment and a status view | Whether separate sessions, isolation and the typed result contract work |
| 3. Core | The ticket system, approval rules, proof and budgets, with a simple scripted assigner | Whether tickets and proof make "done" trustworthy |
| 4. Second harness product | The builder or tester swapped for a different product | Whether the system really is harness-agnostic |
| 5. Config as code and CLI | The schema, plan and apply, and the CLI | Whether a team can be defined and changed safely |
| 6. Coordinator harness | A coordinator replacing the scripted assigner | Whether it plans better than the script or only costs more |
| 7. UI | The ticket board, the proof viewer and the status view | Whether a human can supervise comfortably |
| 8. Domain ownership at length | An owner holding a domain across many sessions, such as customer service | Whether persistence and domain boundaries hold up |

Stage 2 uses one harness product in both roles on purpose. It removes the unknowns of a second product while the loop itself is being built.

## What to measure

The useful question is "what breaks at the boundary", more than "is the output better":

- **Permissions:** what happens when a harness wants approval and nobody is attached.
- **Workspace:** whether owners can share code without collisions.
- **Opacity:** whether problems inside a harness can be debugged and its cost capped.
- **Latency:** how minutes-long tasks behave over A2A streaming.
- **Trust:** how often verified proof agrees with the human's judgment.
- **Overhead:** the size of task below which a single agent is the better choice.

## Open questions

- **Copilot.** Can it run headless or through an SDK? Not verified.
- **A2A support.** Does any harness ship as an A2A server, or is a wrapper always needed? Believed to need a wrapper, not verified.
- **Subscription logins.** Whether a personal subscription may be used for unattended runs, per provider.
- **Budget.** Not part of A2A as far as we know. The format for carrying it, and how a wrapper enforces it, are undecided.
- **Persistence.** How an owner keeps memory across sessions in a way that works for every harness.
- **Domain boundaries.** How one owner requests a change in another's domain.
- **Ticket system.** Build one, or adapt an existing tracker.
- **Config schema.** Not designed.
- **Test environment.** Who starts the app and the browser for UI testing: the core or the tester's wrapper.
- **Choosing a harness per domain.** The working assumption is that tooling and integrations matter more than model preference. Untested.
