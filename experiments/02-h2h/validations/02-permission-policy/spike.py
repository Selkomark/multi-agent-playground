"""Spike 02: can a harness's permission request be answered in code, by policy?

One interactive session per harness, four requests, none of them answered on screen:

    allowed.txt    a policy rule allows it
    denied.txt     a policy rule denies it and tells the model what to do instead
    escalate.txt   no rule: goes to the user queue, the (simulated) user approves
    rejected.txt   no rule: goes to the user queue, the (simulated) user rejects

Usage:
    python spike.py claude
    python spike.py codex
    python spike.py copilot
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "01-session-state"))
import keeper  # noqa: E402

POLICY_HOOK = HERE / "policy_hook.py"
USER_DELAY = 5.0  # seconds the simulated user takes to answer


def prompt_for(name: str, harness: str) -> str:
    text = (
        f"Run this exact shell command with your shell tool: touch {name} . "
        "If a refusal message tells you to run a different command, run that command. "
        "Do not work around a refusal in any other way."
    )
    if harness == "codex":
        # Codex enforces with a sandbox and only asks when the model chooses to escalate.
        # Without this line the model reports the sandbox failure and stops.
        text += " Whenever the sandbox blocks a command, request approval to run it outside the sandbox."
    return text


class PolicyRun(keeper.Run):
    """A keeper run that also plays the user: it answers queued requests after a delay."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.seen: dict[str, float] = {}
        self.answered: list[dict] = []

    def tick(self) -> str:
        state = super().tick()
        now = time.time()
        for request in sorted((self.run_dir / "requests").glob("*.json")) if (self.run_dir / "requests").exists() else []:
            first = self.seen.setdefault(request.name, now)
            reply = self.run_dir / "answers" / request.name
            if now - first >= USER_DELAY and not reply.exists():
                subject = json.loads(request.read_text())["subject"]
                approve = "rejected" not in subject
                reason = "" if approve else "Rejected by the user: this file is not wanted. Do not retry."
                reply.write_text(json.dumps({"approve": approve, "reason": reason}))
                self.answered.append({"subject": subject, "approve": approve})
                print(f"  [{now - self.s.started:6.1f}s] user {'approved' if approve else 'rejected'}: {subject}", flush=True)
        return state


def install_policy_hook(harness: str, run_dir: Path, workspace: Path) -> None:
    command = f"{sys.executable} {POLICY_HOOK} {harness} {run_dir}"
    if harness == "claude":
        path = run_dir / "settings.json"
        settings = json.loads(path.read_text())
        settings["hooks"]["PermissionRequest"] = [
            {"hooks": [{"type": "command", "command": command, "timeout": 120}]}
        ]
    elif harness == "codex":
        path = workspace / ".codex" / "hooks.json"
        settings = json.loads(path.read_text())
        settings["hooks"]["PermissionRequest"] = [
            {"hooks": [{"type": "command", "command": command, "timeout": 120}]}
        ]
    else:
        path = workspace / ".github" / "hooks" / "h2h.json"
        settings = json.loads(path.read_text())
        settings["hooks"]["permissionRequest"] = [{"type": "command", "bash": command, "timeoutSec": 120}]
    path.write_text(json.dumps(settings, indent=2))


def main() -> None:
    harness = sys.argv[1] if len(sys.argv) > 1 else ""
    if harness not in ("claude", "codex", "copilot"):
        sys.exit(__doc__)
    run_dir = HERE / "runs" / f"{datetime.now():%Y%m%d-%H%M%S}-{harness}"
    run_dir.mkdir(parents=True)
    events = run_dir / "events.jsonl"
    workspace = keeper.make_workspace(harness, events, "repo" if harness == "copilot" else "subdir")
    install_policy_hook(harness, run_dir, workspace)
    env = keeper.clean_env(workspace, events)
    names = ["allowed.txt", "denied.txt", "escalate.txt", "rejected.txt"]
    argv = keeper.command_for(harness, prompt_for(names[0], harness), env, allow_work=False, run_dir=run_dir)
    print(f"{harness} / permission policy\n  run {run_dir}", flush=True)

    session = keeper.Session(harness, argv, workspace, env, run_dir, events)
    run = PolicyRun(session, run_dir, accept_trust=harness == "copilot")
    stops = lambda: sum(e["event"] == "Stop" for e in session.hooks())  # noqa: E731
    try:
        for turn, name in enumerate(names, 1):
            if turn > 1:
                run.hold(1.5)
                session.type(prompt_for(name, harness))
            if not run.wait_for(f"turn {turn} to finish", lambda: stops() >= turn and run.state == "idle", 150):
                run.check(f"turn {turn} finished", False, f"state {run.state}: {run.transitions[-1]['reason']}")
                break
    finally:
        run.stop()

    decisions = [json.loads(line) for line in open(run_dir / "decisions.jsonl")] if (run_dir / "decisions.jsonl").exists() else []
    exists = lambda name: (workspace / name).exists()  # noqa: E731
    by = lambda text: [d for d in decisions if text in d["subject"]]  # noqa: E731
    prompts = [
        e for e in session.hooks()
        if e["event"] == "Notification" and (e.get("payload") or {}).get("notification_type") == "permission_prompt"
    ]

    run.check("allow by policy: the action ran", exists("allowed.txt"))
    run.check("deny by policy: the action did not run", not exists("denied.txt"))
    run.check("deny by policy: the model followed the instruction in the refusal", exists("fallback.txt"))
    run.check("no rule, user approves: the action ran", exists("escalate.txt"))
    waited = [d["seconds"] for d in by("escalate") if d["decided_by"] == "user"]
    run.check("no rule: the harness waited for the user's answer", bool(waited) and waited[0] >= USER_DELAY, f"{waited}")
    run.check("no rule, user rejects: the action did not run", not exists("rejected.txt"))
    run.check("no permission prompt reached the screen", not prompts, f"{len(prompts)} prompt notification(s)")
    run.check("every decision came from policy or the user", all(d["decided_by"] in ("policy", "user") for d in decisions))

    result = {
        "harness": harness,
        "passed": all(c["passed"] for c in run.checks),
        "checks": run.checks,
        "decisions": [{k: d[k] for k in ("subject", "decision", "decided_by", "seconds")} for d in decisions],
        "transitions": run.transitions,
        "files": sorted(p.name for p in workspace.glob("*.txt")),
        "seconds": round(time.time() - session.started, 1),
    }
    (run_dir / "result.json").write_text(json.dumps(result, indent=2))
    print("  decisions:")
    for d in result["decisions"]:
        print(f"    {d['decision']:<6} by {d['decided_by']:<7} after {d['seconds']:>5}s  {d['subject']}")
    print(f"  {'PASSED' if result['passed'] else 'FAILED'} in {result['seconds']}s")
    sys.exit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
