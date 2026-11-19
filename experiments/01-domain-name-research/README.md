# Domain Name Research

_Created 2026-11-19_

## Purpose

Build a multi-agent setup that turns a rough description of a business into a list of domain names that can actually be bought, ordered by price.

The question behind it: can agents split by job (naming, per-provider lookup, judging) produce a list that is trustworthy enough to buy from without rechecking every entry by hand?

A second goal is learning. The experiment uses the three current standards for agent systems, each where it fits: ADK for orchestration, A2A between agents, and MCP between an agent and its tools.

## Hypothesis

Splitting the work across agents will give a usable list, because:

- A naming agent that follows explicit guidelines produces better candidates than an open-ended "suggest some names" prompt.
- One agent per domain provider, running at the same time, covers several providers in roughly the time of one, and each agent only has to understand one provider.
- A judge that did not gather the data can compare the providers' answers, spot disagreements and drop names that are not really available.

The main risk is the lookup step: provider APIs need credentials, and their prices may differ from the checkout price.

## Setup

| Agent | What it does | Runs as |
|-------|--------------|---------|
| Naming agent | Proposes candidate domains from the business description, following the naming guidelines | In the orchestrator process |
| Provider agents: `godaddy`, `namecom`, `porkbun`, `registry` | Each checks every candidate at one provider and reports availability and price | One A2A service per provider, called in parallel |
| Judge | Decides which domains to keep and flags anything the buyer should know | In the orchestrator process |

Plain code handles the parts that must be exact: validating the provider reports, dropping taken domains, and sorting by price. See [docs/design.md](docs/design.md).

Prerequisites:

- [uv](https://docs.astral.sh/uv/) and Python 3.12.
- An Anthropic API key for a real run. Every agent uses `claude-opus-5-5` unless `DOMAIN_RESEARCH_MODEL` says otherwise.
- Provider credentials for prices. Without them a provider reports `unknown`; the `registry` agent needs none and reports registration status only.

```bash
uv sync
cp .env.example .env   # then fill in the keys you have
```

## Running

```bash
# Offline: scripted model and made-up quotes. No key, no cost. Shows the whole flow.
uv run domain-research --offline "a subscription service for specialty coffee beans"

# Real run
uv run domain-research "a subscription service for specialty coffee beans"

# Options
uv run domain-research --tlds com,io,co --count 15 --providers porkbun,registry "..."

# Machine-readable output, with the agent logs included
uv run domain-research -o json -l "..."

# Tests
uv run pytest
```

| Flag | Default | Effect |
|------|---------|--------|
| `-o`, `--output` | `text` | `text` prints a table. `json` and `yaml` print one document to stdout with the final list under `result`. |
| `-l`, `--log` | off | Includes the agent logs. In `text` they are printed live above the table. In `json` and `yaml` they are a list under `logs`, each entry with `seconds`, `agent` and `message`. |

In `json` and `yaml` mode stdout holds only the document, so another program can parse it directly. Warnings go to stderr.

A run starts the provider agents, prints the result, and saves everything under `runs/<timestamp>/`:

- `final.json`: the ranked list and the dropped domains.
- `events.jsonl`: every event from every agent, in order.
- `<provider>_agent.log` and `orchestrator.log`: logs and library warnings.

## Results

No real run yet: the pipeline has only been run offline, with a scripted model and made-up quotes. The offline run and the tests confirm the wiring (orchestration, A2A calls, MCP tool calls, ranking, and a provider agent being down). They say nothing about name quality or price accuracy.

Details go in `docs/findings.md` once there are results from real runs.

## Documentation

- [docs/design.md](docs/design.md): architecture and approach
