# Validation 03: Baseline

**Status: in progress.** The runner and the task exist. No results are recorded yet.

## Question

On one task, how do two harness sessions with a ticket handoff compare with one harness using its own sub-agents, in cost and rework?

## Method

One small coding task ([task/SPEC.md](task/SPEC.md)) is done in up to four ways:

| Arm | Setup |
|---|---|
| `single` | One Claude Code session, told to use its own sub-agents to build and to test independently |
| `h2h-claude` | A Claude Code builder session and a separate Claude Code tester session |
| `h2h-codex` | A Claude Code builder and a Codex tester |
| `h2h-copilot` | A Claude Code builder and a Copilot tester |

In the `h2h` arms the tester writes a review file. Failures go back to the builder with the reasons, for up to three rounds.

Every arm is scored by `acceptance.py`, a set of 75 hidden test cases that no harness sees. The score is taken at the builder's first hand-off and at the end. Cost, tokens, rounds and time are recorded per step.

## Running

Each run uses the harnesses' own logins and costs real usage.

```bash
python3 baseline.py single h2h-claude h2h-codex h2h-copilot --repeats 2
python3 baseline.py single --model sonnet
```

Needs Python 3.10 or later, no packages. Output goes to `runs/`, which is not committed.

## Files

- `task/SPEC.md`: the task given to the harnesses.
- `acceptance.py`: the hidden tests.
- `baseline.py`: runs the arms and records cost and scores.
