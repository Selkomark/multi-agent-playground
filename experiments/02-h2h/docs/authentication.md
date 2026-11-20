# Authentication: H2H

Authentication is four separate problems. The first is the likely bottleneck.

| # | Who authenticates to what | Difficulty |
|---|---|---|
| 1 | Each harness to its own model provider | Hardest, and outside our control |
| 2 | H2H to each harness, and the user to H2H's interfaces | Standard, with one sharp edge |
| 3 | Each harness to the resources its domain needs | Design work |
| 4 | The human to the ticket and approval system | Standard, can wait |

## 1. Harness to model provider

Every harness has its own login. Some are interactive and tied to a subscription, some use an API key. Unifying them is where a project like this stalls, so H2H does not try.

**Rule: bring your own login.** Each harness authenticates the way it normally does, with its own credential store. H2H never holds those credentials.

Supporting pieces:

- **Preflight check.** Before a run, H2H confirms each harness is logged in and able to work.
- **Expiry as a status.** If authentication fails mid-task, the ticket becomes blocked with "needs authentication". The work resumes from the ticket once someone fixes the credential. Nothing is lost.

### Unattended runs with Claude

An interactive login is the wrong credential for unattended work, because it can expire while nobody is there to renew it. Claude Code has options meant for this (checked against its documentation on 2026-11-19):

| Option | How | Lifetime | Billing |
|---|---|---|---|
| API key | `ANTHROPIC_API_KEY` | Until revoked | Per use |
| Long-lived token | `claude setup-token`, then `CLAUDE_CODE_OAUTH_TOKEN` | One year | Subscription |
| Key helper | The `apiKeyHelper` setting runs a script that returns a key, re-run on a timer and after an auth failure | As long as the script can produce keys | Depends on the key |
| Cloud provider | Bedrock, Vertex or Foundry credentials | Managed by the provider | Via the provider |

Recommendation: an API key for harness sessions that run unattended.

- It is the documented route for agents built on the Agent SDK, whose documentation says: "Unless previously approved, Anthropic does not allow third party developers to offer claude.ai login or rate limits for their products, including agents built on the Claude Agent SDK." That statement is about products offered to others. It does not rule on personal scripts using one's own subscription, so confirm with Anthropic before relying on the one-year token.
- Per-use billing gives each harness instance a measurable cost, which the budget feature needs.

Details to respect:

- If `ANTHROPIC_API_KEY` is set, it takes precedence over both the one-year token and an interactive login. Set exactly one credential per session.
- `claude setup-token` prints the token once and does not save it.

### Other harnesses

The unattended options for Copilot and Codex have not been checked. Both ran in the validation spikes on the user's existing login, started from a terminal with nobody in an editor.

Gemini CLI is excluded from the project. It no longer offers a personal login, which leaves only an API key or a cloud project, and that does not fit "bring your own login".

## 2. H2H to harness, and user to H2H

- **Local sessions.** H2H reaches each keeper through a local socket, protected by file permissions so only the same operating system user can connect. The reporting tool a harness calls is tied to its own session, so one harness cannot report on another's ticket.
- **The web UI.** `h2h serve` exposes a terminal for every session, which is a remote shell with each harness's permissions. It binds to localhost by default and requires a token. Serving on a network address should be an explicit choice.
- **Remote harnesses.** These are reached over A2A, whose agent cards declare which standard HTTP authentication scheme an agent expects. OAuth client credentials are the likely choice.

## 3. Harness to domain resources

- **Scoped per domain.** The support owner gets a token for the support system and nothing for the deploy pipeline.
- **Referenced in config, never stored there.**
- **Held by the tool, not the model.** Where possible the token lives in the tool server that makes the call, so the model cannot leak it into a ticket or a log.
- **Short-lived** where the provider allows it.

## 4. Human identity

Approvals record who approved. For a single-user local version, the operating system user is enough. Real accounts matter once several people share the system.

## Where to start

A single-user, single-machine version: harnesses use existing logins or an API key, keepers are reached over local sockets, the web UI stays on localhost, and secrets come from the environment. That nearly removes problems 2 and 4 and reduces problem 1 to the preflight check.
