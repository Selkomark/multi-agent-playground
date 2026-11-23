# Validation 01: Session state

_Run 2026-11-20 with Claude Code 2.1.329, GitHub Copilot CLI 1.0.114 and Codex CLI 0.171.0 on macOS._

## Question

Can a keeper tell whether a harness is working, waiting for input, finished or hung, without reading its screen?

## Answer

**Yes, for all three harnesses.** Each one fires its own hooks at the moments that matter, and those were enough to derive every state in every scenario. The reporting tool was not needed for state.

Starting a session unattended is the part that did not work out of the box: each harness has its own idea of a trusted folder, and Claude Code and Copilot stop at a dialog unless the workspace is set up in a specific way.

## Method

`keeper.py` starts one harness in a pseudo-terminal, in a throwaway workspace, and derives its state from four signals:

| Signal | Source |
|---|---|
| Hook events | The harness's own hooks, configured to append a line to an events file |
| Reports | The harness calling `h2h-report`, a stand-in for the H2H reporting tool |
| Terminal activity | Whether any bytes arrive from the terminal. The content is never inspected |
| Process | Whether the harness process is alive |

Three scenarios per harness:

| Scenario | What happens | What must be detected |
|---|---|---|
| `complete` | The harness does a small task and reports. The keeper then types a second task into the terminal, and finally `/exit` | Turn finished, typed prompt accepted, second turn finished, exit |
| `permission` | The harness is asked to run a command that no rule allows | Waiting for input, and that it stays that way |
| `hung` | The harness runs a silent one-minute command, then the keeper freezes the process | Still working during the command, hung once frozen, working again when resumed |

The checks each scenario makes:

| Scenario | Checks |
|---|---|
| `complete` | Turn end is signalled by a hook. The harness called the reporting tool. The file exists. State is idle after the turn. A prompt typed into the terminal is accepted. The second turn finished and reported. The file was changed. The harness exits on `/exit`. Process exit is observed |
| `permission` | A permission prompt is detected. It is detected within 10 seconds of the tool call. State stays "waiting" for 12 seconds while unanswered. The file was not created |
| `hung` | The state stays "working" during 12 seconds of a silent command. A frozen process is detected as hung. The state returns to "working" when the process resumes |

The prompts, in short: `complete` asks for a file `hello.txt` containing "hi" and then the command `h2h-report done first-task`. `permission` asks for `touch needs-approval.txt`. `hung` asks for a program on the PATH that sleeps for a minute and prints nothing. The full text is in `keeper.py`.

Thresholds: a session is "hung" after 15 seconds with no hook event and no terminal bytes while working, and "stalled" after 12 seconds of silence before its first hook event.

## Results

| Scenario | Claude Code | Copilot CLI | Codex CLI |
|---|---|---|---|
| `complete` | Pass | Pass | Pass |
| `permission` | Pass, detected 0.3s after the tool call | Pass, detected 0.3s after the tool call | Pass, detected with the tool call |
| `hung` | Pass, detected after 15s of silence | Pass, detected after 15s of silence | Pass, detected after 15s of silence |

How each state is recognised:

| State | Claude Code | Copilot CLI | Codex CLI |
|---|---|---|---|
| Session started | `SessionStart` hook | `sessionStart` hook | `SessionStart` hook |
| Working | `UserPromptSubmit`, `PreToolUse`, `PostToolUse` hooks | `userPromptSubmitted`, `preToolUse`, `postToolUse` hooks | `UserPromptSubmit`, `PreToolUse`, `PostToolUse` hooks |
| Waiting for a permission answer | `PermissionRequest` hook, then a `Notification` hook of type `permission_prompt` | `notification` hook of type `permission_prompt` | `PermissionRequest` hook |
| Turn finished | `Stop` hook | `agentStop` hook | `Stop` hook |
| Hung | No hook event and no terminal bytes for 15s while working | Same | Same |
| Exited | Process exit, and a `SessionEnd` hook | Process exit, and a `sessionEnd` hook | Process exit. `SessionEnd` fired on `/exit` but not when the process was terminated |

## Findings

### What worked

- **Hooks carry the state.** All three signal session start, prompt accepted, tool start and end, permission prompt, turn end and session end.
- **The reporting tool was called every time.** In every completed turn (two per harness in the final runs) the harness ran `h2h-report` as instructed. The sample is small.
- **Typing into the terminal works.** A second prompt typed by the keeper was accepted by all three, and `/exit` ended all three.
- **A busy harness is never silent.** During a command that printed nothing for a minute, Claude Code sent about 13 KB, Copilot about 7 KB and Codex about 25 KB of terminal bytes in 12 seconds (their progress animation). A frozen process sent none. That makes silence a usable sign of a hang.

### What did not work out of the box

- **Folder trust blocks an unattended start.** Claude Code and Copilot show a dialog before doing anything in a folder they have not been told to trust, and no hook fires until it is answered. Codex started without one inside this repository, which is already marked trusted in its config, and asked in a new repository in the temp directory. Passing the trust setting as a per-launch config override did not remove Codex's dialog.

  | Workspace | Claude Code | Copilot CLI | Codex CLI |
  |---|---|---|---|
  | Plain folder inside a repository the user already trusts | Starts | Asks | Starts |
  | Git worktree of a trusted repository | Starts | Asks, as for any folder in this untrusted repository | Starts |
  | New git repository inside a trusted folder | Asks | Asks | Not tested |
  | New repository in the temp directory | Asks | Not tested | Asks |
  | Any folder that declares hooks in its own settings | Asks, even inside a trusted repository | Asks | Starts, but each hook must be trusted separately |

  Note that this repository was trusted by Claude Code and Codex before the spike, and not by Copilot, so the Copilot column shows an untrusted repository throughout.

  Claude Code's dialog defaults to "No, exit", and Copilot's defaults to "Yes" for this session. The spike got past Copilot's with one Enter sent blind 15 seconds after start (`--accept-trust`). The same key would make Claude Code exit.

- **Hooks are configured differently.** Claude Code takes them on the command line (`--settings`), so nothing executable has to be written into the workspace. Copilot only reads them from the repository root (`.github/hooks/*.json`, or Claude-style in `.claude/settings.json`). In a subfolder of a larger repository, Copilot ignored them. It also reads them from its user folder, `~/.copilot/hooks/`, which needs nothing in the workspace: with `--user-hooks` the keeper installs them there for the run, guarded so they do nothing outside a keeper session, and removes them afterwards. That passed the full `complete` scenario in a worktree. Codex takes hooks in the same format as Claude Code, either from `.codex/hooks.json` in the workspace or at launch as config overrides (`-c hooks.<Event>=...`). In a git worktree it ignored the file and only the launch form worked, so the spike uses that. Codex refuses to run a hook the user has not reviewed unless it is started with `--dangerously-bypass-hook-trust`, which the spike used.

### Things to know

- **The same hook name means different things.** Claude Code and Codex fire `PermissionRequest` only when they are about to ask the user. Copilot fires `permissionRequest` on every tool call, including ones its rules already allow, and signals a prompt on screen with a `permission_prompt` notification. Codex has no notification hook.
- **Codex decides by sandbox, not by allow list.** Inside its sandbox nothing asks. A request is raised only when the model chooses to ask to leave the sandbox, so the permission scenario ran Codex with a read-only sandbox.
- **Turn finished does not mean nothing is running.** Asked to run a one-minute command, Claude Code started it in the background and ended its turn two seconds later.
- **The model picks the tool.** With file writes pre-approved, Claude Code twice wrote a file through a shell redirect, which was not pre-approved, and stopped at a permission prompt. An allow list cannot predict which tool the model chooses. The keeper reported the wait correctly both times.
- **Harnesses have rules of their own.** Claude Code refused to run a bare `sleep 60`, whatever the permission rules said.
- **Silence alone is slow on Copilot.** While its trust dialog was showing, Copilot kept sending terminal bytes for about 100 seconds, so "nothing has happened yet" needs a time limit, not only a silence timer.

## What this changes in the design

- **Hooks become the main status channel.** [../../docs/runtime.md](../../docs/runtime.md) has the reporting tool as the only way status leaves a harness. Hooks give state without relying on the model to remember, so the reporting tool can be kept for content: proof, summaries and requests for a decision.
- **A harness needs hooks to join.** The requirement "runs in a terminal and can call a tool" becomes "runs in a terminal, has lifecycle hooks, and can call a tool".
- **Workspaces need a trust step.** H2H has to create workspaces in a form each harness already trusts (a worktree of a trusted repository worked for Claude Code), or register them as trusted when the user sets H2H up. This belongs in the design as a setup step that the user approves once.
- **Each harness needs an adapter.** Event names, hook file locations, command-line flags, the trust mechanism and the permission model (allow lists or a sandbox) all differ. The adapter is small, but it is not optional.
- **"Idle" needs a second check.** Before treating a finished turn as finished work, H2H should check for background tasks or require a report.

## Limits of this spike

- One machine, one version of each harness, a handful of runs with trivial tasks.
- Claude Code ran on its smallest model, and Copilot and Codex on their default model selection. A different model may report less reliably.
- The keeper answers a terminal's cursor-position query, which some terminal interfaces need at startup. Whether Codex needs it was not tested separately.
- The hang was simulated by freezing the process. A harness stuck in a loop while still animating would not be caught by silence, only by a time or budget limit.
- Recovery after a reboot, long sessions and context compaction were not tested.

## Running

Each run uses the harness's own login and makes a few small model calls.

```bash
python3 keeper.py run claude complete
python3 keeper.py run claude permission
python3 keeper.py run claude hung

python3 keeper.py run codex complete      # same three scenarios

# Copilot needs its own repository for hooks, and the trust dialog answered
python3 keeper.py run copilot complete --workspace repo --accept-trust

# How a harness treats different kinds of workspace
python3 keeper.py run claude complete --workspace worktree
python3 keeper.py run codex complete --workspace worktree
python3 keeper.py run copilot complete --workspace worktree --accept-trust

# Copilot with hooks in its user folder and none in the workspace.
# Adds ~/.copilot/hooks/h2h-spike.json for the run and removes it afterwards.
python3 keeper.py run copilot complete --workspace worktree --accept-trust --user-hooks

# Plain-text view of a run's terminal, for looking into a failure
python3 keeper.py screen runs/<run>/terminal.log
```

Needs Python 3.10 or later, no packages. Each run writes `events.jsonl`, `terminal.log` and `result.json` under `runs/`, which is not committed.

## Files

- `keeper.py`: the keeper, the state rules and the scenarios.
- `hook.py`: the hook target and the `h2h-report` stand-in. Both append to the events file.
