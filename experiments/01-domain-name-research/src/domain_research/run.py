"""Command line entry point.

    uv run domain-research "a subscription service for specialty coffee beans"
    uv run domain-research --offline "anything"     # no API key, no cost, fake data
    uv run domain-research -o json -l "..."         # machine-readable result plus agent logs
"""

import argparse
import asyncio
import json
import logging
import os
import subprocess
import sys
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import httpx
import yaml
from dotenv import load_dotenv
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from .config import PROVIDERS, agent_card_url
from .schemas import FinalList

APP = "domain_research"


def start_provider_agents(providers: list[str], log_dir: Path) -> list[subprocess.Popen]:
    """Start one A2A server per provider and wait until each serves its agent card."""
    processes = []
    for provider in providers:
        log = open(log_dir / f"{provider}_agent.log", "w")
        processes.append(
            subprocess.Popen(
                [sys.executable, "-m", "domain_research.provider_agent", "--provider", provider],
                stdout=log,
                stderr=subprocess.STDOUT,
            )
        )
    deadline = time.time() + 45
    waiting = set(providers)
    while waiting and time.time() < deadline:
        for provider in list(waiting):
            try:
                if httpx.get(agent_card_url(provider), timeout=2).status_code == 200:
                    waiting.discard(provider)
            except httpx.HTTPError:
                pass
        time.sleep(0.5)
    for provider in waiting:
        print(
            f"! {provider} agent did not start (see {log_dir}/{provider}_agent.log); its lookups will be unknown",
            file=sys.stderr,
        )
    return processes


def describe(event) -> str:
    bits = []
    for part in (event.content.parts if event.content else None) or []:
        if part.function_call:
            bits.append(f"calls {part.function_call.name}")
        elif part.function_response:
            bits.append(f"result of {part.function_response.name}")
        elif part.text and not part.thought:
            text = " ".join(part.text.split())
            bits.append(text[:110] + ("..." if len(text) > 110 else ""))
    if event.error_message:
        bits.append(f"ERROR {event.error_message}")
    return "; ".join(bits)


def format_log(entry: dict) -> str:
    return f"[{entry['seconds']:6.1f}s] {entry['agent']:<16} {entry['message']}"


async def research(
    brief: str,
    providers: list[str],
    tlds: list[str],
    count: int,
    run_dir: Path,
    on_log: Callable[[dict], None] | None = None,
) -> FinalList:
    from .pipeline import build_pipeline

    sessions = InMemorySessionService()
    runner = Runner(app_name=APP, agent=build_pipeline(providers, tlds, count), session_service=sessions)
    session = await sessions.create_session(app_name=APP, user_id="local")
    message = types.Content(role="user", parts=[types.Part(text=brief)])

    started = time.time()
    with open(run_dir / "events.jsonl", "w") as trace:
        async for event in runner.run_async(user_id="local", session_id=session.id, new_message=message):
            trace.write(event.model_dump_json(exclude_none=True) + "\n")
            line = describe(event)
            if line and on_log:
                on_log({"seconds": round(time.time() - started, 1), "agent": event.author, "message": line})

    session = await sessions.get_session(app_name=APP, user_id="local", session_id=session.id)
    final = FinalList.model_validate(session.state.get("final") or {"ranked": [], "dropped": []})
    (run_dir / "final.json").write_text(final.model_dump_json(indent=2))
    return final


def print_result(final: FinalList) -> None:
    print("Domains ordered by first-year price")
    print(f"{'#':>2}  {'domain':<26} {'price':>9} {'renewal':>9}  {'provider':<9} notes")
    for i, r in enumerate(final.ranked, 1):
        price = f"{r.price:.2f}" if r.price is not None else "-"
        renewal = f"{r.renewal_price:.2f}" if r.renewal_price is not None else "-"
        others = ", ".join(f"{p} {v:.2f}" for p, v in r.other_prices.items())
        notes = "; ".join(filter(None, [f"also {others}" if others else "", *r.flags]))
        print(f"{i:>2}  {r.domain:<26} {price:>9} {renewal:>9}  {r.provider or '-':<9} {notes}")
    if not final.ranked:
        print("    (none)")
    if final.dropped:
        print("\nDropped")
        for d in final.dropped:
            print(f"    {d.domain:<26} {d.reason}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Research purchasable domain names for a business idea.")
    parser.add_argument("brief", help="rough description of the business")
    parser.add_argument("--tlds", default="com", help="comma-separated endings, for example com,io,co")
    parser.add_argument("--count", type=int, default=12, help="number of candidate names")
    parser.add_argument("--providers", default=",".join(PROVIDERS), help="comma-separated provider names")
    parser.add_argument("--offline", action="store_true", help="use a scripted fake model and fake quotes")
    parser.add_argument(
        "-o", "--output", choices=["text", "json", "yaml"], default="text",
        help="output format (default: text). json and yaml print one document with a 'result' key",
    )
    parser.add_argument(
        "-l", "--log", action="store_true",
        help="include the agent logs: printed live in text mode, under a 'logs' key in json and yaml",
    )
    args = parser.parse_args()

    load_dotenv()
    if args.offline:
        os.environ["DOMAIN_RESEARCH_OFFLINE"] = "1"
    elif not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY is not set. Put it in .env, or pass --offline for a run with fake data.")

    providers = [p for p in args.providers.split(",") if p]
    unknown = [p for p in providers if p not in PROVIDERS]
    if unknown:
        sys.exit(f"Unknown provider(s): {', '.join(unknown)}. Known: {', '.join(PROVIDERS)}")
    tlds = [t.strip().lstrip(".") for t in args.tlds.split(",") if t.strip()]

    run_dir = Path("runs") / datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir.mkdir(parents=True)
    # Library warnings go to a file so the console shows only the agent trace.
    logging.basicConfig(filename=run_dir / "orchestrator.log", level=logging.INFO)
    logging.captureWarnings(True)
    text = args.output == "text"
    logs: list[dict] = []

    def on_log(entry: dict) -> None:
        logs.append(entry)
        if text and args.log:
            print(format_log(entry), flush=True)

    processes = start_provider_agents(providers, run_dir)
    try:
        final = asyncio.run(research(args.brief, providers, tlds, args.count, run_dir, on_log))
    finally:
        for process in processes:
            process.terminate()

    if text:
        print_result(final)
        print(f"\nTrace and result saved in {run_dir}/")
        if args.offline:
            print("Offline run: names, availability and prices above are fake.")
        return

    # json and yaml: stdout carries exactly one document, so a caller can parse it directly.
    document: dict = {"result": final.model_dump()}
    if args.log:
        document["logs"] = logs
    if args.output == "json":
        print(json.dumps(document, indent=2))
    else:
        print(yaml.safe_dump(document, sort_keys=False, allow_unicode=True), end="")


if __name__ == "__main__":
    main()
