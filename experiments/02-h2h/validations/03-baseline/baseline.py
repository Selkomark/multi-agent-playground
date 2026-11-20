"""Spike 03: one task, done two ways.

    single        one Claude Code session, told to use its own sub-agents to build and test
    h2h-<tester>  a Claude Code builder session and a separate tester session (claude,
                  codex or copilot), passing work through a ticket: the tester writes a
                  review, failures go back to the builder with reasons, up to MAX_ROUNDS

Both are scored by hidden acceptance tests that no harness sees.

Usage:
    python baseline.py single h2h-claude h2h-codex h2h-copilot --repeats 2
    python baseline.py single --model sonnet

Every run uses the harnesses' own logins and costs real usage.
"""

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = HERE / "task" / "SPEC.md"
MAX_ROUNDS = 3
TIMEOUT = 300   # seconds allowed per harness call
LINGER = 15     # seconds a process may stay alive after it has printed its result

SINGLE_PROMPT = """Read SPEC.md in this folder and implement it.

Work the way a small team would: have one sub-agent build durations.py, and have a different
sub-agent, which did not write the code, test it against SPEC.md with tests of its own and
report defects. Fix what it finds and have it check again. Finish when the independent tester
finds no defects. Do not ask me questions; decide and proceed."""

BUILD_PROMPT = """You are the builder. Read SPEC.md in this folder and implement durations.py.
Check your own work as you normally would. A separate tester will review it after you.
Do not ask questions; decide and proceed. When done, reply with a one-paragraph summary."""

TEST_PROMPT = """You are the tester. You did not write this code. Read SPEC.md and test durations.py
in this folder against it, with tests of your own that you write and run. Do not edit durations.py.

When you are done, write a file named review.json in this folder, exactly in this form:

{"verdict": "pass" or "fail", "defects": [{"description": "...", "example": "input, expected, actual"}]}

Use "pass" only if you found no way in which the code departs from SPEC.md. Do not ask questions."""

FIX_PROMPT = """The tester reviewed durations.py and reported these defects:

{defects}

Fix durations.py so it follows SPEC.md. If you believe a reported defect is wrong, leave that
behaviour as it is and say why. Reply with a one-paragraph summary of what you changed."""

RETEST_PROMPT = """The builder has changed durations.py after your last review (your previous
review.json is in this folder). Test it again against SPEC.md, including the earlier defects,
and overwrite review.json in the same form as before. Do not edit durations.py."""


def clean_env() -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith(("CLAUDE", "CMUX", "ANTHROPIC_"))}
    env["PATH"] = ":".join(p for p in env.get("PATH", "").split(":") if "cmux-cli-shims" not in p)
    return env


ENV = clean_env()


def binary(name: str) -> str:
    found = shutil.which(name, path=ENV["PATH"])
    if not found:
        sys.exit(f"{name} is not on PATH")
    return found


def call(argv: list[str], cwd: Path, log: Path, done_marker: str | None = None) -> tuple[str, float, str]:
    """Run one harness call. Returns its output, the seconds it took, and how it ended:

        ok        the process exited by itself
        lingered  it printed its result (done_marker) but did not exit, and was stopped
        timeout   it was stopped at TIMEOUT without a result
    """
    started = time.time()
    out_path = log.parent / f"call-{time.time_ns()}.out"
    status = "ok"
    with open(out_path, "w") as out, open(log, "a") as err:
        err.write(f"\n$ {' '.join(a if len(a) < 80 else '<prompt>' for a in argv)}\n")
        err.flush()
        process = subprocess.Popen(
            argv, cwd=cwd, env=ENV, stdin=subprocess.DEVNULL, stdout=out, stderr=err, start_new_session=True
        )
        finished_at = None
        while process.poll() is None:
            time.sleep(0.5)
            now = time.time()
            if done_marker and finished_at is None and done_marker in out_path.read_text(errors="replace"):
                finished_at = now
            if finished_at and now - finished_at > LINGER:
                status = "lingered"
            elif now - started > TIMEOUT:
                status = "timeout"
            else:
                continue
            try:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=10)
            except (ProcessLookupError, subprocess.TimeoutExpired):
                process.kill()
            break
    seconds = (finished_at or time.time()) - started
    return out_path.read_text(errors="replace"), seconds, status


def run_claude(prompt: str, cwd: Path, log: Path, model: str, resume: str | None = None) -> dict:
    argv = [
        binary("claude"), "-p", prompt, "--output-format", "stream-json", "--verbose", "--model", model,
        "--permission-mode", "acceptEdits", "--setting-sources", "project", "--max-budget-usd", "3",
        "--allowedTools", "Bash(python3:*),Bash(python:*),Bash(ls:*),Bash(cat:*)",
    ]
    if resume:
        argv += ["--resume", resume]
    out, seconds, status = call(argv, cwd, log, done_marker='"total_cost_usd"')
    data = None
    for line in out.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if isinstance(event, dict) and event.get("type") == "result":
            data = event
    if data is None:
        return {"harness": "claude", "seconds": round(seconds, 1), "ended": status, "error": f"no result ({status})"}
    usage = data.get("usage") or {}
    return {
        "harness": "claude",
        "seconds": round(seconds, 1),
        "ended": status,
        "usd": data.get("total_cost_usd"),
        "turns": data.get("num_turns"),
        "input_tokens": (usage.get("input_tokens") or 0)
        + (usage.get("cache_read_input_tokens") or 0)
        + (usage.get("cache_creation_input_tokens") or 0),
        "output_tokens": usage.get("output_tokens"),
        "session": data.get("session_id"),
        "error": data.get("result", "")[:300] if data.get("is_error") else None,
    }


def run_codex(prompt: str, cwd: Path, log: Path) -> dict:
    argv = [binary("codex"), "exec", "--json", "--sandbox", "workspace-write", "--skip-git-repo-check", prompt]
    out, seconds, status = call(argv, cwd, log)
    tokens_in = tokens_out = 0
    for line in out.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        usage = event.get("usage") if isinstance(event, dict) else None
        if usage:
            tokens_in += usage.get("input_tokens") or 0
            tokens_out += usage.get("output_tokens") or 0
    result = {"harness": "codex", "seconds": round(seconds, 1), "ended": status,
              "input_tokens": tokens_in, "output_tokens": tokens_out}
    if status == "timeout":
        result["error"] = "timeout"
    return result


def run_copilot(prompt: str, cwd: Path, log: Path) -> dict:
    usage_file = log.parent / f"copilot-usage-{time.time_ns()}.json"
    argv = [
        binary("copilot"), "-p", prompt, "--silent", "--trust-folder",
        "--allow-tool=write", "--allow-tool=shell(python3:*)", "--allow-tool=shell(python:*)",
        f"--usage-output-file={usage_file}",
    ]
    _, seconds, status = call(argv, cwd, log)
    result: dict = {"harness": "copilot", "seconds": round(seconds, 1), "ended": status}
    if status == "timeout":
        result["error"] = "timeout"
    if usage_file.exists():
        result["usage"] = json.loads(usage_file.read_text())
    return result


def run_tester(tester: str, prompt: str, cwd: Path, log: Path, model: str, resume: str | None) -> dict:
    if tester == "claude":
        return run_claude(prompt, cwd, log, model, resume)
    return run_codex(prompt, cwd, log) if tester == "codex" else run_copilot(prompt, cwd, log)


def score(workspace: Path) -> dict:
    out = subprocess.run(
        [sys.executable, str(HERE / "acceptance.py"), str(workspace)], capture_output=True, text=True, timeout=120
    )
    try:
        return json.loads(out.stdout)
    except ValueError:
        return {"passed": 0, "total": 0, "failed": [f"acceptance run failed: {out.stderr[-300:]}"]}


def read_review(workspace: Path) -> dict:
    try:
        review = json.loads((workspace / "review.json").read_text())
        return {"verdict": review.get("verdict"), "defects": review.get("defects") or []}
    except (OSError, ValueError):
        return {"verdict": "missing", "defects": []}


def new_workspace(run_dir: Path) -> Path:
    workspace = run_dir / "workspace"
    workspace.mkdir(parents=True)
    shutil.copy(SPEC, workspace / "SPEC.md")
    return workspace


def arm_single(run_dir: Path, model: str) -> dict:
    workspace = new_workspace(run_dir)
    step = run_claude(SINGLE_PROMPT, workspace, run_dir / "harness.log", model)
    return {"steps": [{"role": "single", **step}], "rounds": 1, "final": score(workspace)}


def arm_h2h(run_dir: Path, model: str, tester: str) -> dict:
    workspace = new_workspace(run_dir)
    log = run_dir / "harness.log"
    steps = []
    build = run_claude(BUILD_PROMPT, workspace, log, model)
    steps.append({"role": "builder", "round": 1, **build})
    first = score(workspace)
    reviews = []
    tester_session = None
    rounds = 0
    for rounds in range(1, MAX_ROUNDS + 1):
        (workspace / "review.json").unlink(missing_ok=True) if rounds == 1 else None
        prompt = TEST_PROMPT if rounds == 1 else RETEST_PROMPT
        test = run_tester(tester, prompt, workspace, log, model, tester_session)
        tester_session = test.get("session")
        steps.append({"role": "tester", "round": rounds, **test})
        review = read_review(workspace)
        reviews.append({"round": rounds, "verdict": review["verdict"], "defects": len(review["defects"]),
                        "hidden_score_at_review": score(workspace)["passed"]})
        if review["verdict"] != "fail" or rounds == MAX_ROUNDS:
            break
        defects = "\n".join(f"- {d.get('description')} ({d.get('example')})" for d in review["defects"])
        fix = run_claude(FIX_PROMPT.format(defects=defects), workspace, log, model, build.get("session"))
        steps.append({"role": "builder", "round": rounds + 1, **fix})
    return {"steps": steps, "rounds": rounds, "first_handoff": first, "reviews": reviews, "final": score(workspace)}


def summarise(arm: str, outcome: dict) -> dict:
    steps = outcome["steps"]
    claude = [s for s in steps if s["harness"] == "claude"]
    return {
        "arm": arm,
        "score": f"{outcome['final']['passed']}/{outcome['final']['total']}",
        "first_handoff": (
            f"{outcome['first_handoff']['passed']}/{outcome['first_handoff']['total']}"
            if "first_handoff" in outcome else None
        ),
        "rounds": outcome["rounds"],
        "claude_usd": round(sum(s.get("usd") or 0 for s in claude), 4),
        "builder_usd": round(sum(s.get("usd") or 0 for s in claude if s["role"] != "tester"), 4),
        "tokens": sum((s.get("input_tokens") or 0) + (s.get("output_tokens") or 0) for s in steps),
        "seconds": round(sum(s["seconds"] for s in steps)),
        "lingered": sum(s.get("ended") == "lingered" for s in steps),
        "errors": [s["error"] for s in steps if s.get("error")],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("arms", nargs="+", choices=["single", "h2h-claude", "h2h-codex", "h2h-copilot"])
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--model", default="haiku", help="Claude model for the builder and the single arm")
    args = parser.parse_args()

    batch = HERE / "runs" / f"{datetime.now():%Y%m%d-%H%M%S}-{args.model}"
    rows = []
    for repeat in range(1, args.repeats + 1):
        for arm in args.arms:
            run_dir = batch / f"{arm}-{repeat}"
            run_dir.mkdir(parents=True)
            print(f"{arm} #{repeat} ...", flush=True)
            outcome = arm_single(run_dir, args.model) if arm == "single" else arm_h2h(run_dir, args.model, arm[4:])
            (run_dir / "outcome.json").write_text(json.dumps(outcome, indent=2))
            row = {"repeat": repeat, "model": args.model, **summarise(arm, outcome)}
            rows.append(row)
            print(f"  score {row['score']}  first hand-off {row['first_handoff']}  rounds {row['rounds']}  "
                  f"claude ${row['claude_usd']}  tokens {row['tokens']}  {row['seconds']}s  lingered {row['lingered']}"
                  + (f"  ERRORS {row['errors']}" if row["errors"] else ""), flush=True)
            if outcome["final"]["failed"]:
                print(f"  failed: {outcome['final']['failed'][:8]}", flush=True)
    (batch / "summary.json").write_text(json.dumps(rows, indent=2))
    print(f"summary: {batch / 'summary.json'}")


if __name__ == "__main__":
    main()
