# Runtime: H2H

How H2H runs harnesses as processes: sessions, workspaces, monitoring, jumping in, and surviving a crash.

## Role

H2H is a harness supervisor as well as a coordinator. It starts each harness, gives it a workspace, tracks its session, keeps its logs, and lets the user watch or step into it. The closest comparisons are tmux for the sessions and Docker for the listing, logs and "open a terminal inside it" experience.

## Process model

```mermaid
flowchart TD
    CLI(["h2h CLI"]) --> ORCH
    UI(["Web UI<br/>h2h serve"]) --> ORCH

    subgraph CORE["<b>H2H orchestrator</b>"]
        ORCH["Orchestrator<br/>process"]
        STATE[("State directory<br/>and ticket store")]
        ORCH --- STATE
    end

    subgraph S1["<b>Session: builder</b>"]
        K1["Keeper"] --> H1["Harness in<br/>pseudo-terminal"]
    end

    subgraph S2["<b>Session: tester</b>"]
        K2["Keeper"] --> H2["Harness in<br/>pseudo-terminal"]
    end

    ORCH <-->|Local socket| K1
    ORCH <-->|Local socket| K2

    classDef entry fill:#1f2937,stroke:#9ca3af,stroke-width:1.5px,color:#ffffff
    classDef harness fill:#dbeafe,stroke:#2563eb,stroke-width:1.5px,color:#111827
    classDef code fill:#dcfce7,stroke:#16a34a,stroke-width:1.5px,color:#111827
    classDef store fill:#fef3c7,stroke:#d97706,stroke-width:1.5px,color:#111827
    class CLI,UI entry
    class H1,H2 harness
    class ORCH,K1,K2 code
    class STATE store
```

Each harness runs under its own keeper process, which is independent of the orchestrator and records its state on disk. The orchestrator talks to keepers over local sockets, so it can stop and start again without disturbing a running harness.

### Orchestrator

The process that applies the rules: it assigns tickets, enforces approvals and budgets, and serves the CLI and the web UI. It holds no state that exists only in memory. Everything it needs is in the state directory and the ticket store.

### Keeper

A small process that sits between H2H and one harness. Docker calls the equivalent a shim.

- **Owns the harness.** It holds the pseudo-terminal and the harness process. It is detached from the orchestrator, so an orchestrator crash does not affect it.
- **Records state on disk.** Session ID, workspace path, ticket, status, exit code and the terminal log.
- **Offers a socket for attaching** to the terminal.
- **Stays tiny.** If a keeper dies, its harness dies with it, so the keeper does nothing beyond holding the terminal and writing state.

The keeper is the `h2h` binary started in an internal mode, so there is still only one file to ship.

### State directory

One entry per session, written by its keeper, plus the ticket store (for example SQLite). Because listing, logs and attaching read from here and from the keepers' sockets, they keep working even when the orchestrator is not running.

## Sessions and workspaces

- **Session.** One running harness with its own history. H2H records the harness's own session ID so the session can be resumed later.
- **Workspace.** Each session gets its own working copy, for example a git worktree, so two sessions never edit the same files. H2H creates it when the session starts and removes or archives it when the session ends.
- **The same harness twice.** Two sessions of one product are two keepers with separate workspaces and histories.

## How H2H and a harness communicate

Reading a harness's status off its terminal screen is fragile, so H2H never does that. The harness reports to H2H instead.

| Direction | Channel |
|---|---|
| Work into the harness | The prompt when the session starts, and occasionally text typed into its terminal |
| Status out of the harness | A reporting tool that H2H provides, as an `h2h` command or an MCP server. The harness calls it to say "ticket done, here is the proof" or "blocked, need a decision" |
| People | The terminal, for watching and jumping in |

The requirement for a harness to join a team is therefore small: it runs in a terminal and it can call a tool.

## Monitoring and jumping in

| Mode | What the user gets | When |
|---|---|---|
| Watch | The live terminal and log of a session, read-only | Monitoring |
| Attach | The user types into the harness's terminal, as with tmux | Intervening in a running session |
| Take over | H2H pauses the session, the user works in the harness's own interactive CLI on the same session and workspace, then hands it back | Longer manual work. Depends on the harness supporting resume by session ID |

Attach is the main path. Two rules apply to all three:

- **One driver at a time.** A session is driven by H2H or by the user, never both. Attaching to type puts the session's ticket on hold until the user releases it.
- **Interventions are recorded** on the ticket, so the record of who did what stays accurate.

## Crash recovery

```mermaid
flowchart TD
    START(["h2h starts"]) --> SCAN["Scan state<br/>directory"]
    SCAN --> FOUND{"Sessions<br/>found?"}
    FOUND -->|No| FRESH(["Fresh team"])
    FOUND -->|Yes| ASK{"Rejoin or<br/>start fresh?"}
    ASK -->|Rejoin| RECON["Reconnect keepers,<br/>reread tickets"]
    RECON --> RESUME(["Business<br/>as usual"])
    ASK -->|Fresh| OLD{"Stop old<br/>sessions?"}
    OLD -->|Yes| STOP["Stop sessions"]
    OLD -->|No| LEAVE["Leave running,<br/>detached"]
    STOP --> FRESH
    LEAVE --> FRESH

    classDef entry fill:#1f2937,stroke:#9ca3af,stroke-width:1.5px,color:#ffffff
    classDef action fill:#dbeafe,stroke:#2563eb,stroke-width:1.5px,color:#111827
    classDef check fill:#dcfce7,stroke:#16a34a,stroke-width:1.5px,color:#111827
    class START,FRESH,RESUME entry
    class SCAN,RECON,STOP,LEAVE action
    class FOUND,ASK,OLD check
```

On start, H2H looks for sessions that outlived the previous run and lets the user rejoin them or begin again. Rejoining needs nothing from the harnesses, because they never stopped.

When scanning, H2H sorts each session into one of three groups:

- **Running:** the keeper answers on its socket.
- **Exited while H2H was down:** the keeper recorded an exit code and whatever the harness last reported.
- **Stale:** state on disk with no live keeper, to be cleaned up.

What this does not cover:

- **A reboot.** Processes die with the machine. Recovery then depends on each harness resuming by session ID.
- **Spending while the orchestrator is down.** Harnesses keep working with nobody enforcing budgets. A keeper can be set to pause its harness when it has not heard from the orchestrator for a set time.
- **A keeper crash.** Its harness is lost, which is why the keeper is kept minimal.

## Interfaces

H2H is a command-line tool first. The web UI is the same tool started with a flag.

| Command (names not final) | Does |
|---|---|
| `h2h` | Starts or rejoins a team |
| `h2h ps` | Lists active sessions with harness, domain, ticket and state |
| `h2h logs -f <session>` | Follows one session's log |
| `h2h attach <session>` | Opens the session's terminal |
| `h2h serve --port <n>` | Serves the web UI, including a terminal in the browser for each session |

The web UI offers what the CLI does, plus the ticket board and proof viewer described in [configuration.md](configuration.md). A terminal in the browser is a remote shell with the harness's permissions; see [authentication.md](authentication.md).

## Implementation

**Language: Go.**

- **Single file.** Go compiles to one self-contained executable, with the web UI's files embedded in it, and cross-compiles for other systems from one machine.
- **Fits the work.** H2H supervises processes and relays streams. Its speed is set by the models, which take seconds to minutes, so a faster language would not show.
- **Established for this shape of tool.** Docker, Kubernetes and the GitHub CLI are written in Go.

Rust would also work and also ships as one file. It was set aside because its speed advantage does not matter here and development is slower.

**What a compiled binary protects.** It contains no source code, which stops casual inspection. It is not opaque:

- Function names, file paths and text strings are readable by default. Build flags that strip debug information and paths, and an obfuscating build tool, reduce this.
- A determined person can still reverse-engineer the logic. No secrets go in the binary.

**Platforms.** macOS and Linux first. Pseudo-terminals and local sockets work differently on Windows.
