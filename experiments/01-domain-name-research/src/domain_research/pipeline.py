"""The orchestrator: naming agent -> provider agents in parallel (A2A) -> judge -> ranking.

    naming_agent      LLM   proposes candidate domains            -> state["candidates"]
    provider_checks   A2A   one remote agent per provider, at the same time
    collector         code  validates the provider reports        -> state["quotes_json"]
    judge             LLM   decides which domains to keep and why -> state["verdicts"]
    ranker            code  applies hard rules, sorts by price    -> state["final"]
"""

import json
from collections.abc import AsyncGenerator

from google.adk.agents import BaseAgent, LlmAgent, ParallelAgent, SequentialAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent
from google.adk.events import Event, EventActions
from google.genai import types
from pydantic import ValidationError

from .config import agent_card_url, generation_config, make_model
from .schemas import (
    CandidateList,
    DroppedDomain,
    FinalList,
    ProviderReport,
    Quote,
    RankedDomain,
    VerdictList,
)

NAMING_INSTRUCTION = """You are the naming agent in a domain research pipeline.

The user describes a business. Propose {count} candidate domain names for it,
using only these endings: {tlds}.

Guidelines for every name:
- Easy to memorize: short, few syllables, nothing that needs explaining.
- It may sound like a real word but be spelled differently. Respelled words
  are often still unregistered when the dictionary spelling is taken.
- Easy to say and type: someone who hears it once can type it. No hyphens, no digits.
- It fits the business: it suggests what the business does or how it should feel.

Obvious dictionary words on .com are almost always taken, so favor names that
are plausibly still free. Vary your approach across the list. Do not claim
that any name is available; other agents check that."""

JUDGE_INSTRUCTION = """You are the judge in a domain research pipeline.

A naming agent proposed these candidates:
{candidates_json}

Provider agents then looked each one up. These are their quotes:
{quotes_json}

A status of "unknown" means the provider gave no answer; it is not evidence
either way. The provider "registry" reports registration status only and
never has a price.

Give one verdict per candidate domain:
- keep=false if any provider reports it taken, or if the name is a poor fit
  for the business or likely to be confused with an existing well-known brand.
- keep=true otherwise.
- Use flags for things the buyer should know: providers disagreeing, a premium
  listing, a renewal price far above the first-year price, no provider
  confirming availability.

Do not restate prices and do not order the list. Code does both afterwards."""


def _load(model, value):
    """Parse state that may hold a dict, a JSON string, or nothing."""
    try:
        if isinstance(value, str):
            return model.model_validate_json(value)
        return model.model_validate(value)
    except ValidationError:
        return None


def _event(ctx: InvocationContext, author: str, text: str, state: dict) -> Event:
    return Event(
        invocation_id=ctx.invocation_id,
        author=author,
        branch=ctx.branch,
        content=types.Content(role="model", parts=[types.Part(text=text)]),
        actions=EventActions(state_delta=state),
    )


def send_candidates(ctx: InvocationContext, agent_name: str, to_a2a_part):
    """Build the A2A message for a provider agent: just the list of domains."""
    candidates = _load(CandidateList, ctx.session.state.get("candidates"))
    domains = [c.domain.lower() for c in candidates.candidates] if candidates else []
    text = "Check these domains:\n" + json.dumps({"domains": domains})
    return [to_a2a_part(types.Part(text=text))], None


def parse_report(text: str) -> ProviderReport | None:
    start = text.find("{")
    return _load(ProviderReport, text[start:]) if start >= 0 else None


class Collector(BaseAgent):
    """Turns the provider agents' replies into one validated table of quotes."""

    providers: list[str]

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        candidates = _load(CandidateList, ctx.session.state.get("candidates")) or CandidateList(candidates=[])
        domains = list(dict.fromkeys(c.domain.lower() for c in candidates.candidates))

        answers: dict[tuple[str, str], Quote] = {}
        for event in ctx.session.events:
            if event.invocation_id != ctx.invocation_id or not event.content:
                continue
            provider = (event.author or "").removesuffix("_agent")
            if provider not in self.providers:
                continue
            for part in event.content.parts or []:
                report = parse_report(part.text or "")
                for quote in report.quotes if report else []:
                    quote.provider = provider
                    answers[(provider, quote.domain.lower())] = quote

        quotes = [
            answers.get((p, d))
            or Quote(domain=d, provider=p, status="unknown", note="no answer from the provider agent")
            for d in domains
            for p in self.providers
        ]
        answered = sum(q.status != "unknown" for q in quotes)
        yield _event(
            ctx,
            self.name,
            f"{len(domains)} domains x {len(self.providers)} providers: {answered} of {len(quotes)} lookups answered.",
            {
                "candidates_json": candidates.model_dump_json(),
                "quotes_json": json.dumps([q.model_dump() for q in quotes]),
            },
        )


def rank(candidates: CandidateList, quotes: list[Quote], verdicts: VerdictList | None) -> FinalList:
    """Apply the hard rules and order by price. Plain code, so the result is reproducible."""
    verdict_by_domain = {v.domain.lower(): v for v in verdicts.verdicts} if verdicts else {}
    ranked: list[RankedDomain] = []
    dropped: list[DroppedDomain] = []
    seen: set[str] = set()
    for candidate in candidates.candidates:
        domain = candidate.domain.lower()
        if domain in seen:
            continue
        seen.add(domain)
        mine = [q for q in quotes if q.domain.lower() == domain]
        taken = [q.provider for q in mine if q.status == "taken"]
        verdict = verdict_by_domain.get(domain)
        if taken:
            dropped.append(DroppedDomain(domain=domain, reason=f"taken according to {', '.join(taken)}"))
            continue
        if verdict and not verdict.keep:
            dropped.append(DroppedDomain(domain=domain, reason=f"judge: {verdict.reason}"))
            continue
        available = [q for q in mine if q.status == "available"]
        if not available:
            dropped.append(DroppedDomain(domain=domain, reason="no provider confirmed availability"))
            continue
        priced = sorted((q for q in available if q.price is not None), key=lambda q: q.price)
        best = priced[0] if priced else None
        flags = list(verdict.flags) if verdict else ["the judge gave no verdict"]
        if not best:
            flags.append("unregistered, but no provider returned a price")
        ranked.append(
            RankedDomain(
                domain=domain,
                provider=best.provider if best else None,
                price=best.price if best else None,
                renewal_price=best.renewal_price if best else None,
                currency=best.currency if best else "USD",
                other_prices={q.provider: q.price for q in priced[1:]},
                name_reasoning=candidate.reasoning,
                judge_reason=verdict.reason if verdict else "",
                flags=flags,
            )
        )
    ranked.sort(key=lambda r: (r.price is None, r.price or 0, r.domain))
    return FinalList(ranked=ranked, dropped=dropped)


class Ranker(BaseAgent):
    """Combines verdicts and quotes into the final price-ordered list."""

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        candidates = _load(CandidateList, state.get("candidates_json")) or CandidateList(candidates=[])
        quotes = [Quote.model_validate(q) for q in json.loads(state.get("quotes_json") or "[]")]
        final = rank(candidates, quotes, _load(VerdictList, state.get("verdicts")))
        yield _event(
            ctx,
            self.name,
            f"{len(final.ranked)} domains ranked, {len(final.dropped)} dropped.",
            {"final": final.model_dump()},
        )


def build_pipeline(providers: list[str], tlds: list[str], count: int) -> SequentialAgent:
    naming = LlmAgent(
        name="naming_agent",
        model=make_model(),
        generate_content_config=generation_config(),
        instruction=NAMING_INSTRUCTION.format(count=count, tlds=", ".join("." + t for t in tlds)),
        output_schema=CandidateList,
        output_key="candidates",
    )
    remotes = [
        RemoteA2aAgent(
            name=f"{provider}_agent",
            agent_card=agent_card_url(provider),
            context_builder=send_candidates,
            timeout=180,
        )
        for provider in providers
    ]
    judge = LlmAgent(
        name="judge",
        model=make_model(),
        generate_content_config=generation_config(),
        instruction=JUDGE_INSTRUCTION,
        output_schema=VerdictList,
        output_key="verdicts",
    )
    return SequentialAgent(
        name="domain_research",
        sub_agents=[
            naming,
            ParallelAgent(name="provider_checks", sub_agents=remotes),
            Collector(name="collector", providers=providers),
            judge,
            Ranker(name="ranker"),
        ],
    )
