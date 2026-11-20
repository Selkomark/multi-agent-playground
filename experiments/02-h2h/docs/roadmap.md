# Roadmap: H2H

Nothing here is scheduled. This is the order the design suggests, and the questions that must be answered before planning a build.

## Before any build

Use Gas Town and CLI Agent Orchestrator for long enough to decide whether to build H2H or to build on one of them. See [prior-art.md](prior-art.md).

## Stages

Each stage gives a baseline for judging the next.

| Stage | What is built | What it tells us |
|---|---|---|
| 1. One session | The `h2h` binary, a keeper running one harness in a terminal with its own workspace, plus list, logs and attach | Whether a harness can be supervised, watched and entered |
| 2. Crash recovery | State on disk and rejoin on restart | Whether sessions survive H2H stopping, and what is lost |
| 3. Reporting tool | The tool a harness calls to fetch work and report status and proof, tried on a task that needs a harness (change code in a repo and run the tests) | Whether harnesses report reliably without the terminal being parsed |
| 4. Build and test loop | Two sessions of the same harness as builder and tester, with the commit handoff and a test environment | Whether separate sessions, isolation and the typed result contract work |
| 5. Core | The ticket store in kanban mode, approval rules, proof, budgets, path ownership and the merge queue, with a simple scripted assigner. Usage is recorded per ticket from here on | Whether tickets and proof make "done" trustworthy, and what a ticket costs |
| 6. Second harness product | The builder or tester swapped for a different product | Whether the system really is harness-agnostic |
| 7. Config as code | The schema, plan and apply | Whether a team can be defined and changed safely |
| 8. Coordination tiers | Small agents for routing and checks, then a coordinator harness as escalation, replacing the scripted assigner | Whether the tiers plan better than the script, and how often the harness is needed |
| 8a. Managed mode | The project manager, estimation, sprints bounded by budget, and the computed retro report | Whether planning overhead pays for itself, from planning share and rework share |
| 9. Web UI | `h2h serve`: the ticket board, proof viewer, status view and browser terminals | Whether a human can supervise comfortably |
| 10. Domain ownership at length | An owner holding a domain across many sessions, such as customer service | Whether persistence and domain boundaries hold up |
| 11. Remote harnesses | A harness on another machine behind an A2A wrapper | Whether the contract holds across machines |

Stage 4 uses one harness product in both roles on purpose. It removes the unknowns of a second product while the loop itself is being built.

## What to measure

The useful question is "what breaks at the boundary", more than "is the output better":

- **Permissions:** what happens when a harness wants approval and nobody is attached.
- **Workspace:** whether owners can share code without collisions.
- **Reporting:** how often a harness fails to report, and what that looks like from outside.
- **Recovery:** whether a rejoined team continues correctly after a crash.
- **Intervention:** whether stepping into a session and handing it back leaves the ticket record accurate.
- **Trust:** how often verified proof agrees with the human's judgment.
- **Cost:** cost per approved ticket, and the share spent on coordination, planning and rework.
- **Estimates:** how far actuals are from estimates, and whether that improves over sprints.
- **Overhead:** the size of task below which a single agent is the better choice.

## Open questions

- **Copilot and Gemini.** Whether each runs in a terminal session that H2H can start, prompt and resume. Not verified.
- **Typing work into a terminal.** How reliably follow-up instructions can be delivered to a running harness this way, per product.
- **Session resume.** Which harnesses can resume by session ID, needed for take over and for recovery after a reboot. Claude Code can.
- **Subscription logins.** Whether a personal subscription may be used for unattended runs, per provider.
- **Budget.** How H2H measures what a harness spends, given that each product reports usage differently.
- **A2A for Go.** Whether an official A2A library for Go exists and is current. Believed so, not verified. Only matters for remote harnesses.
- **Keeper pause.** How a keeper pauses a harness safely when the orchestrator is unreachable.
- **Persistence.** How an owner keeps memory across sessions in a way that works for every harness.
- **Domain boundaries.** How one owner requests a change in another's domain.
- **Ticket system.** Build one, or adapt an existing tracker. Beads, the tracker behind Gas Town, is built for agents and worth evaluating.
- **Sub-agent visibility.** Whether an owner's sub-agents can be made visible to H2H without breaking harness-agnosticism.
- **Domain size.** How to tell that a domain is too big for one owner before it becomes a problem.
- **Domain contracts.** The format of the written interface between domains, and how dependents are notified of a change.
- **Path ownership.** How shared files, such as dependency manifests, are owned.
- **Model and effort mapping.** How ticket settings translate for each harness, and which harnesses can change them at all.
- **Ticket similarity.** Whether domain, phase and a type label are enough to compare tickets for suggestions.
- **Small agents.** Which framework, if any, and which model.
- **Estimation budget.** How much an owner may spend to estimate a ticket, and the size below which estimation is skipped.
- **Config schema.** Not designed.
- **Test environment.** Who starts the app and the browser for UI testing: H2H or the tester's session.
- **Windows.** Out of scope at first. Pseudo-terminals and local sockets differ there.
- **Choosing a harness per domain.** The working assumption is that tooling and integrations matter more than model preference. Untested.
