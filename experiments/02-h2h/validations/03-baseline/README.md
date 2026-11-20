# Validation 03: Baseline

_Run 2026-11-20 with Claude Code 2.1.329 (Haiku 5.5), GitHub Copilot CLI 1.0.114 and Codex CLI 0.171.0 on macOS._

## Question

On one task, how do two harness sessions with a ticket handoff compare with one harness using its own sub-agents, in cost and rework?

## Answer

**On a small task, separate sessions cost about the same as one harness with sub-agents, and no more time.** The overhead the hypothesis expected did not show up at this size.

**A tester from a different product found real defects that everything else missed.** Codex and Copilot each caught a genuine departure from the spec in code that had passed the builder's own checks, a same-model tester and all 75 hidden tests.

The sample is small (two or three runs per setup, one easy task), so these are indications, not measurements.

## Method

One small coding task, a duration parser and formatter ([task/SPEC.md](task/SPEC.md)), done four ways:

| Arm | Setup |
|---|---|
| `single` | One Claude Code session, told to use its own sub-agents to build and to test independently |
| `h2h-claude` | A Claude Code builder session and a separate Claude Code tester session |
| `h2h-codex` | A Claude Code builder and a Codex tester |
| `h2h-copilot` | A Claude Code builder and a Copilot tester |

In the `h2h` arms the tester writes a review file. Failures go back to the builder with the reasons, for up to three rounds. All harnesses run in their non-interactive mode, with five minutes allowed per call.

Every arm is scored by `acceptance.py`, a set of 75 hidden test cases that no harness sees. The score is taken at the builder's first hand-off and at the end.

### The hidden tests

The cases were checked against a reference solution before use.

| Group | Cases | Examples |
|---|---|---|
| Valid input parses to the right value | 22 | `1w2d3h4m5s6ms`, `1H30M`, `0.0005s` is 1, `-2.5ms` is -3, `0` |
| Invalid input raises `ValueError` | 21 | `30m1h`, `1h2h`, `1.5h30m`, `1 h`, `10`, `+1h`, `.5h`, `1e3s` |
| Wrong type raises `TypeError` | 5 | `None`, `5`, `1.5`, bytes, a list |
| Formatting gives the canonical string | 11 | 5400000 is `1h30m`, 0 is `0s`, 691200000 is `1w1d` |
| Formatting a wrong type raises `TypeError` | 5 | `None`, a string, `1.5`, `True`, `False` |
| Round trip: parse of format returns the input | 11 | 0, -1, 86399999, 123456789012 |

### The prompts

| Role | Instruction, in short |
|---|---|
| `single` | Implement the spec. Have one sub-agent build and a different sub-agent test with its own tests, fix what it finds, and finish when the tester finds no defects |
| Builder | Implement the spec and check your own work. A separate tester will review it |
| Tester | You did not write this code. Test it against the spec with tests you write and run, do not edit it, and write `review.json` with a verdict and a list of defects |
| Builder, after a failed review | Here are the reported defects. Fix the code to follow the spec, or say why a report is wrong |

The full text of each prompt is at the top of `baseline.py`.

## Results

| Arm | Run | Hidden tests at first hand-off | Final | Rounds | Claude cost | Other usage | Time |
|---|---|---|---|---|---|---|---|
| `single` | trial | n/a | 75/75 | 1 | $0.038 | | 155s |
| `single` | 1 | n/a | 75/75 | 1 | $0.048 | | 184s |
| `single` | 2 | n/a | 75/75 | 1 | $0.028 | | 81s |
| `h2h-claude` | 1 | 75/75 | 75/75 | 1 | $0.023 | | 98s |
| `h2h-claude` | 2 | 75/75 | 75/75 | 1 | $0.025 | | 111s |
| `h2h-codex` | 1 | 75/75 | 75/75 | 2 | $0.015 | Codex: 173k tokens in, 2.9k out | 111s |
| `h2h-codex` | 2 | 75/75 | 75/75 | 1 | $0.007 | Codex: 77k tokens in, 1.3k out | 63s |
| `h2h-copilot` | 1 | 75/75 | 75/75 | 2 | $0.028 | Copilot: 0.68 AI credits | 158s |
| `h2h-copilot` | 2 | 75/75 | 75/75 | 1 | $0.007 | Copilot: 0.24 AI credits | 64s |

"Claude cost" covers every Claude session in the arm. In the Codex and Copilot arms that is the builder only, and the tester's usage is in the next column in that product's own unit, so those arms cannot be compared with the others on total cost.

## Findings

### Cost and time

- **No coordination penalty at this size.** The single arm cost $0.028 to $0.048 and the two-session Claude arm $0.023 to $0.025. The ranges overlap, and the single arm varied more between runs than the arms differed from each other.
- **Time was similar.** 81 to 184 seconds for the single arm, 98 to 111 for two Claude sessions.
- **A rework round roughly doubled the builder's cost** in the runs where a tester sent work back ($0.015 against $0.007 with Codex, $0.028 against $0.007 with Copilot).

### Quality and rework

- **The builder was right first time by the hidden tests, every time.** All six builder hand-offs scored 75/75. The task is too easy for this model to show a difference in the final score.
- **The same-model tester passed everything.** In both `h2h-claude` runs the Claude tester found nothing.
- **The other products' testers each found a real defect once.** Neither was covered by the hidden tests:
  - **Codex:** the unit pattern was case-insensitive, so it accepted the Unicode long s (`ſ`) as `s`, and then failed with a `KeyError` where the spec requires a `ValueError`.
  - **Copilot:** numbers longer than 4300 digits failed on Python's integer conversion limit, which breaks the spec's rule that every integer round-trips.
- **Both were fixed in one round**, and the tester then passed the work. In the second run of each arm the builder's code did not have the flaw and the tester passed it first time.

This is two findings in four cross-product runs, against none in two same-model runs. It fits the hypothesis that work is better checked by someone who did not produce it, and suggests that a different product is a more independent checker than a second session of the same one. It is far too few runs to be sure.

### Running harnesses without a terminal

- **A finished session may not exit.** In the first attempt the single arm finished its work in 80 seconds and its `claude -p` process then stayed alive until it was killed at the time limit. It had been started with its input left open. Closing the input fixed it, and the runner now also stops any process that stays alive after printing its result. H2H cannot treat "the process exited" as the only sign that a non-interactive run is done.
- **Usage is reported in three different units:** dollars and tokens (Claude Code), tokens only (Codex), and AI credits with a token breakdown (Copilot). The budget feature in [../../docs/cost.md](../../docs/cost.md) needs a conversion per harness, or budgets per harness in its own unit.

## What this changes in the design

- **The cost worry is smaller than assumed for the handoff itself.** A second session and a review file did not cost more than sub-agents inside one session. The expensive designs in [../../docs/prior-art.md](../../docs/prior-art.md) spend on coordination between many agents, which this spike did not exercise.
- **Pairing different products for build and test has a concrete argument now.** It is worth making "the tester is a different product from the builder" a recommended default, and measuring it properly.
- **Hidden tests are not ground truth.** Both real defects were outside them. "Proof verified by H2H" catches what the checks cover and nothing else, so an independent reviewer still adds something on top.
- **Rework needs a cost line of its own.** A round sent back by a tester is the largest swing in cost seen here.

## Limits of this spike

- One task, easy for the model, two or three runs per arm. Run-to-run variation is as large as the differences between arms.
- The single arm's sub-agents and the separate sessions used the same Claude model. A stronger or weaker model may change which arm wins.
- The H2H arms had none of the real H2H machinery: no ticket store, no keeper, no approval step. The handoff was a file and a script.
- Coordination among more than two sessions, where prior tools report high cost, was not tested.
- The defects found were edge cases. Whether a different-product tester catches defects that matter more is not shown.

A fairer version would use a task hard enough for the builder to get wrong, at least five runs per arm, and a tester of each product against the same builder output.

## Running

Each run uses the harnesses' own logins and costs real usage. The nine runs above cost about $0.22 on Claude, plus the Codex and Copilot usage shown.

```bash
python3 baseline.py single h2h-claude h2h-codex h2h-copilot --repeats 2
python3 baseline.py single --model sonnet
```

Needs Python 3.10 or later, no packages. Output goes to `runs/`, which is not committed.

## Files

- `task/SPEC.md`: the task given to the harnesses.
- `acceptance.py`: the hidden tests.
- `baseline.py`: runs the arms and records cost, rounds and scores.
