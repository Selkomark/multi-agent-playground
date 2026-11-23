# Prior art: H2H

The idea is not new. Several open-source projects orchestrate multiple coding harnesses, and a few combine most of the pieces H2H uses. This document records what exists and where H2H intends to differ. H2H takes ideas from them and no code; see [Clean-room rule](#clean-room-rule).

Found by web search on 2026-11-20, mostly from secondary write-ups. None of these tools has been used or read in source as part of this experiment, so every detail needs confirming against the project itself.

## Existing projects

| Project | What it does | Overlap with H2H |
|---|---|---|
| [Gas Town](https://github.com/gastownhall/gastown) (Steve Yegge, released January 2026) | Runs many coding agents in parallel in tmux, with a coordinating session and git-backed work tracking through its companion issue tracker, Beads. Written in Go. Reported to support Claude Code, Copilot, Codex and Gemini | The closest overall: a coordinator, a ticket system built for agents, terminal sessions, Go |
| [CLI Agent Orchestrator](https://github.com/awslabs/cli-agent-orchestrator) (AWS Labs) | A supervisor agent delegates to worker agents, each in its own tmux window, communicating through MCP tools. Supervisor and workers can be different CLIs | Supervisor and workers across different harnesses, with tool-based reporting |
| [Claude Squad](https://agentwiki.org/_export/xhtml/claude_squad) | A Go terminal app that runs Claude Code, Codex, Gemini and others in tmux sessions with a git worktree each | Sessions, workspaces, listing and attaching, harness-agnostic |
| [Kagan](https://raw.githubusercontent.com/kagan-sh/kagan-legacy/main/README.md) | A kanban terminal app where agents work in worktrees and nothing reaches the main branch without explicit human approval | The ticket board as a human approval gate |
| [Vibe Kanban](https://www.blog.brightcoding.dev/2026/07/17/vibe-kanban-the-revolutionary-ai-agent-manager-every-dev-needs), [Cline Kanban](https://cline.bot/blog/announcing-kanban), [agtx](https://awesome.ecosyste.ms/projects/github.com%2Ffynnfluegge%2Fagtx) | Kanban boards that dispatch tasks to different coding agent CLIs | Tickets across mixed harnesses |

Smaller session managers of the same kind include [coders](https://github.com/jayphen/coders), [workmux](https://github.com/mic92/workmux) and [Agent Orchestrator](https://www.mintlify.com/ComposioHQ/agent-orchestrator).

## Lessons taken

- **The problem is real.** Several people arrived at the same shape independently.
- **Cost is the known weakness.** Gas Town is described as running 20 to 30 agents in parallel and needing several subscriptions, and its author is quoted calling it a "cash guzzler". [cost.md](cost.md) is H2H's response.
- **Terminal sessions with worktrees are the common base.** H2H does the same, with its own keeper in place of a tmux dependency.

## Where H2H intends to differ

These did not appear in the search results. They were not searched for one by one, so they may exist elsewhere.

- **Domain ownership.** Existing tools hand out tasks, usually one per worktree. H2H gives a harness an area to own long-term.
- **Proof-gated approval by risk.** Automatic approval on verified proof for low-risk work, with humans on the rest.
- **Cost as a design constraint.** One owner per domain, three tiers of coordination, no idle sessions.
- **Config as code with plan and apply.**
- **Optional managed planning** with estimation, untimed sprints bounded by budget, and a computed retro.
- **Sessions that survive without tmux,** inside a single binary.

## Clean-room rule

H2H is written from scratch. It is not an extension, a fork or a wrapper of any project listed here, and none of their code is copied into it. The reason is copyright: code lifted from another project brings that project's licence and ownership with it, and a company auditing H2H should find nothing of that kind.

| Allowed | Not allowed |
|---|---|
| Using the same architecture or approach as an existing tool, where it fits | Copying their source code into H2H, in any amount |
| Reading their documentation, write-ups and source to understand how they work | Pasting their code and editing it to fit, or translating it line by line into another language |
| Reimplementing a part of their solution in our own code, written for H2H | Taking over their files as they are: configuration, schemas, prompts or tests |
| Using them as a user, to see how an approach works in practice | Depending on them as a library, a subprocess or a required companion tool |

Ideas and architecture are free to use. Code is not. Where an idea is taken from one of these projects, the design document says so and names the project.

The rules for third-party libraries are in [licensing.md](licensing.md).

## Using the existing tools

Trying Gas Town and CLI Agent Orchestrator as a user is still worthwhile, to learn what works and what hurts in practice. It no longer decides whether to build: H2H is built either way.

## Sources

- [Gas Town repository](https://github.com/gastownhall/gastown)
- [Gas Town research notes](https://rywalker.com/research/gastown)
- [What Happens When You Let 6 AI Agents Write Code at the Same Time](https://lakshminp.substack.com/p/6-ai-agents-coding-experiment)
- [AWS Labs CLI Agent Orchestrator](https://github.com/awslabs/cli-agent-orchestrator)
- [CLI Agent Orchestrator documentation](https://awslabs.github.io/cli-agent-orchestrator/docs/intro)
- [Claude Squad overview](https://agentwiki.org/_export/xhtml/claude_squad)
- [Kagan README](https://raw.githubusercontent.com/kagan-sh/kagan-legacy/main/README.md)
- [Vibe Kanban write-up](https://www.blog.brightcoding.dev/2026/07/17/vibe-kanban-the-revolutionary-ai-agent-manager-every-dev-needs)
- [Cline Kanban announcement](https://cline.bot/blog/announcing-kanban)
- [The best AI agent orchestration tools for coding in 2026](https://crystl.dev/blog/best-ai-agent-orchestration-tools/)
