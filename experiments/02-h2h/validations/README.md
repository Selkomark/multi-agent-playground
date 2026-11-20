# Validations: H2H

Short spikes that test the assumptions most likely to invalidate the H2H design, before any build is planned. The reasons are in [../docs/risks.md](../docs/risks.md).

A spike is throwaway code that answers one question. It is not the start of H2H, and it is written in whatever gets the answer fastest.

## Spikes

| # | Spike | Question | Status |
|---|---|---|---|
| 01 | Session state | Can H2H tell whether a harness is working, waiting for input, finished or hung, without reading its screen? | Not run |
| 02 | Permission policy | Can a harness's permission request be answered in code, by policy, with allow, deny and "ask the user"? | Not run |
| 03 | Baseline | On one task, how do two harness sessions with a ticket handoff compare with one harness using its own sub-agents, in cost and rework? | Not run |

Each spike gets its own directory (`01-session-state/` and so on) with a README that states the question, the method, how to run it and the result.

## Harnesses under test

The harness products installed on the test machine: Claude Code and GitHub Copilot CLI. Others (Gemini, Codex) are not installed and are not covered.

## What a result changes

| If this fails | Then |
|---|---|
| 01 for a harness | That harness cannot be supervised unattended. The communication model in [../docs/runtime.md](../docs/runtime.md) needs another signal, or the harness is excluded |
| 02 for a harness | That harness's prompts can only be answered by attaching. It is limited to pre-approved work; see [../docs/permissions.md](../docs/permissions.md) |
| 03 shows no benefit | The hypothesis in the experiment README is wrong for that size of task, and the experiment should say where, or whether, H2H pays off |
