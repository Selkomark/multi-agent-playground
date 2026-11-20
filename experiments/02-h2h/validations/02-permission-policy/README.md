# Validation 02: Permission policy

_Run 2026-11-20 with Claude Code 2.1.329, GitHub Copilot CLI 1.0.114 and Codex CLI 0.171.0 on macOS._

## Question

Can a harness's permission request be answered in code, by policy, with allow, deny and "ask the user", so that nobody has to answer a prompt in its terminal?

## Answer

**Yes, for all three harnesses.** Each has a permission-request hook that accepts an allow or a deny with a message. One policy script answered every request in an interactive session, and no permission prompt reached the screen.

This is layers 2 and 3 of [../../docs/permissions.md](../../docs/permissions.md). Layer 1, generating each harness's own rules, was not tested here.

## Method

`policy_hook.py` is registered on each harness's permission-request hook. It reads the request, looks it up in `policy.json`, and answers:

| Policy says | What the hook does |
|---|---|
| Allow | Answers allow. The action runs |
| Deny | Answers deny, with a message for the model |
| No rule | Puts the request in a queue and waits. A simulated user answers after five seconds, and the hook passes that answer on. With no answer within 60 seconds it denies |

`spike.py` runs one interactive session per harness and asks for four commands in turn, playing the user for the queue:

| Request | Policy | Expected |
|---|---|---|
| `touch allowed.txt` | Allow | File created |
| `touch denied.txt` | Deny, with "create fallback.txt instead" | No `denied.txt`, and `fallback.txt` created |
| `touch escalate.txt` | No rule, user approves | File created after the user's answer |
| `touch rejected.txt` | No rule, user rejects | No file |

## Results

| Check | Claude Code | Copilot CLI | Codex CLI |
|---|---|---|---|
| Allow by policy: the action ran | Pass | Pass | Pass |
| Deny by policy: the action did not run | Pass | Pass | Pass |
| Deny by policy: the model followed the instruction in the refusal | Pass | Pass | Pass |
| No rule, user approves: the action ran | Pass | Pass | Pass |
| No rule: the harness waited for the answer (about 5s) | Pass | Pass | Pass |
| No rule, user rejects: the action did not run | Pass | Pass | Pass |
| No permission prompt reached the screen | Pass | Pass | Pass (see below) |

Policy decisions took under 0.1 seconds. While a request waited for the user, the harness simply waited, with its hook still running.

For Codex, "no prompt reached the screen" rests on the session carrying on after each answer with nobody typing. Codex has no hook that reports a prompt being shown.

## Findings

### What worked

- **One hook, one answer format per harness.** Claude Code and Codex take the same JSON (`hookSpecificOutput.decision.behavior`). Copilot takes a flatter one (`behavior`). All three accept a message with a deny.
- **A deny can redirect the work.** The deny message reached the model word for word, and all three then ran the alternative command it named. The alternative went through the hook as its own request.
- **Waiting for a person works inside the hook.** The hook can hold a request while the user decides. During that time H2H knows exactly what is being asked, because it holds the request itself.

### Things to know

- **Codex only asks when the model chooses to.** Codex enforces with a sandbox. A blocked command fails, and a permission request is raised only if the model then asks to run it outside the sandbox. In the first run the model reported the failure and stopped, so nothing reached the hook. It asked reliably once the prompt told it to request approval when the sandbox blocks a command. An H2H instruction file for Codex needs that line.
- **Copilot's hook sees every tool call.** Its permission hook fires even for actions its own rules allow, so the policy is consulted on everything. Claude Code and Codex only consult it for what their own rules did not settle.
- **Wording matters after a deny.** With the first prompt wording ("do what the refusal says and nothing more"), Codex read the refusal and stopped without running the alternative. The deny message should state the next step as a plain instruction, and the session's standing instructions should say that such instructions are to be followed.
- **Hook timeouts set the limit on waiting.** The spike set 120 seconds. The documented defaults are 600 seconds for Claude Code and Codex and 30 seconds for Copilot, and Copilot's documentation says a timed-out hook lets the normal flow continue, which would put a prompt on screen. A person may take hours.

### Not tested

- **A long wait.** What each harness does when the user takes longer than the hook timeout. The likely design is to deny with "waiting for approval", park the ticket, and resume the session when the answer arrives.
- **Generated native rules** (layer 1), and how they combine with the hook.
- **Tools other than the shell:** file edits, web access and MCP tools.
- **Non-interactive mode**, and sub-agents started by the harness.
- **A hook that crashes.** The documentation differs per harness on whether that allows or denies.
- **Containment.** An approved Codex command ran outside its sandbox. Nothing here limits what an approved action can reach.

## What this changes in the design

- **The permission design holds.** The three layers in [../../docs/permissions.md](../../docs/permissions.md) can be built on all three harnesses tested, and the "Not verified" items there about a hook that answers in code and a deny the model acts on are now answered for these three.
- **"Waiting for permission" becomes H2H's own state.** With the hook in place a harness never shows a prompt. The wait is a request in H2H's queue, which is more reliable than detecting a prompt from outside.
- **Each harness needs standing instructions**, written by its adapter: follow instructions in a refusal, and for Codex, ask for approval when the sandbox blocks a command.
- **Long waits need a design.** A request that outlives the hook timeout has to be denied and retried later, which ties the permission queue to the ticket system.

## Running

Each run uses the harness's own login and makes a few small model calls.

```bash
python3 spike.py claude
python3 spike.py codex
python3 spike.py copilot
```

Needs Python 3.10 or later, no packages. It reuses the keeper from [../01-session-state/](../01-session-state/README.md). Each run writes `decisions.jsonl`, `events.jsonl`, `terminal.log` and `result.json` under `runs/`, which is not committed.

## Files

- `policy.json`: the rules used in the spike.
- `policy_hook.py`: the hook. It answers from policy or from the user queue.
- `spike.py`: runs the session and plays the user.
