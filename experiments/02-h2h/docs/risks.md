# Risks and gaps: H2H

What the design does not yet answer, found in a review before any build. Each entry says what is missing and the direction proposed. Three were then tested; see the last section. The other directions are untested.

Permissions were the largest gap and have their own document: [permissions.md](permissions.md).

## Could block the build

| Gap | Why it matters | Proposed direction |
|---|---|---|
| **Session state** | H2H must tell whether a harness is working, waiting for input, finished or hung. The design relies on the harness calling the reporting tool, and a harness that forgets looks idle | Combine several signals, none of them read from the screen: the reporting tool, the harness's own hooks for "turn finished" and "needs input", the process exit, and a silence timer as the last resort |
| **Shared usage limits** | Several sessions on one subscription or API key draw from one quota. Three owners on one login can reach the limit three times faster and all stop together | Treat the quota as a shared resource per login: limit concurrent sessions per login, and hold tickets when a limit is hit instead of failing them |
| **Context lifetime** | An owner holds a domain for weeks, but a session's context fills up and is compacted or restarted. Where the owner's knowledge lives between sessions is not designed | Keep domain knowledge in files in the workspace (a domain notes file plus the ticket history), so any new session can load it. Do not depend on one harness's own memory feature |
| **Shared machine resources** | Separate working copies separate files only. Two sessions that start the same dev server, test database or port collide | H2H hands out ports and database names per session through environment variables. Containers per session solve this and containment together |

## Could make results untrustworthy

| Gap | Why it matters | Proposed direction |
|---|---|---|
| **Who verifies proof** | [governance.md](governance.md) asks for test output "from a run the author did not control" but does not say who runs it. If the harness runs its own tests, proof is self-reported | H2H runs the declared check itself, in a clean checkout of the reported commit, and stores the output as the proof |
| **Instructions between harnesses** | Text one harness writes on a ticket becomes instructions for another. Content that one harness read from the web or a customer message can steer another, which is worse once approvals are automatic | Tickets carry structured fields, with free text marked as untrusted data. Owners that read outside content get narrower automatic approvals |
| **No baseline** | The roadmap compares each stage with the one before. It never compares H2H with one harness using its own sub-agents on the same task, which is what the hypothesis claims to beat | Run the same task both ways before building, and again at stages 4 and 6 |

## Can wait, but must be designed

| Gap | Why it matters | Proposed direction |
|---|---|---|
| **The user as bottleneck** | Approvals and permission requests wait for the user, and nothing says how the user learns something is waiting | A single queue of things waiting for the user, with notifications, and an away setting that decides whether waiting work is held or denied |
| **Hung sessions and circular waits** | A session can loop without reporting, and two owners can each wait on the other | A time limit and a hard budget stop per ticket, and a check for tickets blocked on each other that escalates to the user |
| **Harness updates** | A new version of a harness can change its flags, hooks or terminal behaviour | One small adapter per harness, with a conformance test that runs when the harness version changes |

## Validation before a build

Three of these could invalidate the design, so they were tested first, as short spikes under [`../validations/`](../validations/README.md). The results are in [findings.md](findings.md).

| Gap | Spike | Outcome |
|---|---|---|
| Session state | 01 | Answered. Hooks give the state on Claude Code, Copilot and Codex. A new gap appeared: folder trust stalls an unattended start |
| Permissions | 02 | Answered for short waits. A hook can allow, deny with instructions, and hold a request for the user. Long waits are untested |
| No baseline | 03 | Partly answered. No cost penalty for two sessions on a small task, on a small sample. A harder task and more runs are needed |

Every other gap in this document is still open.
