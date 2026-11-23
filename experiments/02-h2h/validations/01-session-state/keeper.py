"""Spike 01: can a keeper tell what state a harness is in without reading its screen?

Runs one harness (Claude Code, Codex CLI or Copilot CLI) in a pseudo-terminal, in a throwaway
workspace, and derives its state from signals that need no screen parsing:

    - hook events the harness fires itself (configured in the workspace)
    - calls to the reporting tool (`h2h-report`)
    - whether the terminal is producing any bytes at all (activity, not content)
    - whether the process is alive

Usage:
    python keeper.py run <claude|codex|copilot> <complete|permission|hung>
    python keeper.py screen <terminal.log>      # for a human debugging a run

Every run uses the harness's real login and makes a few small model calls.
"""

import argparse
import fcntl
import json
import os
import re
import select
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import termios
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
HOOK = HERE / "hook.py"

# Hook events registered per harness, under each harness's own names.
HOOK_EVENTS = {
    "claude": [
        "SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "PostToolUseFailure",
        "PermissionRequest", "Notification", "Stop", "SessionEnd",
    ],
    "codex": [
        "SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "PermissionRequest",
        "Stop", "SessionEnd",
    ],
    "copilot": [
        "sessionStart", "sessionEnd", "userPromptSubmitted", "preToolUse", "postToolUse",
        "errorOccurred", "agentStop", "subagentStop", "permissionRequest", "notification",
    ],
}

# Copilot's names mapped to the names the keeper reasons about.
CANONICAL = {
    "sessionStart": "SessionStart", "sessionEnd": "SessionEnd",
    "userPromptSubmitted": "UserPromptSubmit", "preToolUse": "PreToolUse",
    "postToolUse": "PostToolUse", "agentStop": "Stop", "subagentStop": "SubagentStop",
    "permissionRequest": "PermissionRequest", "notification": "Notification",
    "errorOccurred": "Error",
}

# Claude Code fires PermissionRequest only when it is about to ask the user. Copilot
# fires it for every tool call, including ones its rules already allow, so there it
# says nothing about whether a prompt is on screen.
PERMISSION_HOOK_MEANS_PROMPT = {"claude": True, "codex": True, "copilot": False}

HUNG_AFTER = 15.0          # seconds with no event and no terminal bytes while working
START_STALL_AFTER = 12.0   # seconds of silence before the first event


# ---------------------------------------------------------------- workspace

def clean_env(workspace: Path, events: Path) -> dict:
    """The child's environment: no trace of the session that launched this spike."""
    env = {k: v for k, v in os.environ.items() if not k.startswith(("CLAUDE", "CMUX", "ANTHROPIC_"))}
    path = [p for p in env.get("PATH", "").split(":") if "cmux-cli-shims" not in p]
    env["PATH"] = ":".join([str(workspace / "bin"), *path])
    env["TERM"] = "xterm-256color"
    env["H2H_EVENTS"] = str(events)
    return env


def make_workspace(harness: str, events: Path, kind: str, user_hooks: bool = False) -> Path:
    """A fresh folder for the harness to work in. The kind decides how it relates to
    folders the user has already trusted, which decides whether a trust dialog appears.

        subdir    plain folder inside this (trusted) repository
        repo      its own git repository, inside this repository's folder
        worktree  a git worktree of this repository, placed in the run directory
        temp      its own git repository in the system temp directory
    """
    run_dir = events.parent
    workspace = run_dir / "workspace"
    if kind == "temp":
        workspace = Path(tempfile.mkdtemp(prefix=f"h2h-spike-{harness}-")).resolve()
    elif kind == "worktree":
        subprocess.run(
            ["git", "worktree", "add", "-q", "--detach", str(workspace)], cwd=HERE, check=True
        )
    else:
        workspace.mkdir()
    if kind in ("repo", "temp"):
        subprocess.run(["git", "init", "-q"], cwd=workspace, check=True)
    (workspace / "README.md").write_text("Scratch workspace for an H2H validation spike.\n")

    def hook(name: str) -> dict:
        command = f"{sys.executable} {HOOK} hook {events} {name}"
        return {"hooks": [{"type": "command", "command": command}]}

    # Claude Code takes hooks on the command line (--settings), which keeps executable
    # config out of the workspace: a folder that declares hooks triggers the trust
    # dialog even under a trusted parent. Copilot reads hooks from the repository only.
    if harness == "claude":
        settings = {"hooks": {name: [hook(name)] for name in HOOK_EVENTS[harness]}}
        (events.parent / "settings.json").write_text(json.dumps(settings, indent=2))
    elif harness == "codex":
        # Codex uses the same schema as Claude Code. It also takes hooks at launch, as
        # config overrides, which works in a worktree where a .codex/hooks.json file in
        # the workspace was not loaded. The hooks are kept here and turned into
        # arguments by command_for. Its per-hook trust is skipped with a flag.
        settings = {"hooks": {name: [hook(name)] for name in HOOK_EVENTS[harness]}}
        (events.parent / "hooks.json").write_text(json.dumps(settings, indent=2))
    elif not user_hooks:
        native = {
            "version": 1,
            "hooks": {
                name: [{
                    "type": "command",
                    "bash": f"{sys.executable} {HOOK} hook {events} {name}",
                    "timeoutSec": 10,
                }]
                for name in HOOK_EVENTS[harness]
            },
        }
        (workspace / ".github" / "hooks").mkdir(parents=True)
        (workspace / ".github" / "hooks" / "h2h.json").write_text(json.dumps(native, indent=2))

    bin_dir = workspace / "bin"
    bin_dir.mkdir()
    report = bin_dir / "h2h-report"
    report.write_text(f'#!/bin/sh\nexec {sys.executable} {HOOK} report {events} "$@"\n')
    report.chmod(0o755)
    # A silent command that takes a minute. Claude Code refuses a bare `sleep`.
    slow = bin_dir / "slow-task"
    slow.write_text(f'#!/bin/sh\nexec {sys.executable} -c "import time; time.sleep(60)"\n')
    slow.chmod(0o755)
    return workspace


def command_for(harness: str, prompt: str, env: dict, allow_work: bool, run_dir: Path) -> list[str]:
    binary = shutil.which(harness, path=env["PATH"])
    if not binary:
        sys.exit(f"{harness} is not on PATH")
    if harness == "claude":
        allowed = "Bash(h2h-report:*)" + (",Write,Edit,Bash(slow-task:*)" if allow_work else "")
        return [
            binary, "--allowedTools", allowed, "--permission-mode", "manual",
            "--setting-sources", "project", "--settings", str(run_dir / "settings.json"),
            "--model", "haiku", prompt,
        ]
    if harness == "codex":
        # Codex decides by sandbox, not by allow list: inside the sandbox nothing asks,
        # and leaving it needs approval. A read-only sandbox makes any write ask.
        # The events file sits outside the workspace, so the run directory is made
        # writable too. A read-only sandbox does not accept extra writable folders.
        sandbox = ["--sandbox", "workspace-write", "--add-dir", str(run_dir)] if allow_work else ["--sandbox", "read-only"]
        hooks: list[str] = []
        for name, groups in json.loads((run_dir / "hooks.json").read_text())["hooks"].items():
            handlers = ",".join(
                "{" + ",".join(f"{key}={json.dumps(value)}" for key, value in handler.items()) + "}"
                for group in groups for handler in group["hooks"]
            )
            hooks += ["-c", f"hooks.{name}=[{{hooks=[{handlers}]}}]"]
        return [
            binary, *hooks, "--dangerously-bypass-hook-trust", "--ask-for-approval", "on-request", *sandbox, prompt,
        ]
    rules = ["--allow-tool=shell(h2h-report:*)"]
    if allow_work:
        rules += ["--allow-tool=write", "--allow-tool=shell(slow-task:*)"]
    return [binary, *rules, "-i", prompt]


COPILOT_USER_HOOKS = Path.home() / ".copilot" / "hooks" / "h2h-spike.json"


def install_copilot_user_hooks() -> bool:
    """Put the keeper's hooks in Copilot's user folder, so the workspace holds none.

    Each hook does nothing unless H2H_EVENTS is set, which only the keeper sets, so
    the user's own Copilot sessions are unaffected. Returns whether the folder was
    created, so the caller can remove exactly what was added.
    """
    if COPILOT_USER_HOOKS.exists():
        sys.exit(f"{COPILOT_USER_HOOKS} already exists; not overwriting it")
    created = not COPILOT_USER_HOOKS.parent.exists()
    COPILOT_USER_HOOKS.parent.mkdir(parents=True, exist_ok=True)
    hooks = {
        name: [{
            "type": "command",
            "bash": f'[ -n "$H2H_EVENTS" ] || exit 0; exec {sys.executable} {HOOK} hook "$H2H_EVENTS" {name}',
            "timeoutSec": 10,
        }]
        for name in HOOK_EVENTS["copilot"]
    }
    COPILOT_USER_HOOKS.write_text(json.dumps({"version": 1, "hooks": hooks}, indent=2))
    return created


def remove_copilot_user_hooks(created_folder: bool) -> None:
    COPILOT_USER_HOOKS.unlink(missing_ok=True)
    if created_folder:
        try:
            COPILOT_USER_HOOKS.parent.rmdir()
        except OSError:
            pass


# ---------------------------------------------------------------- session

class Session:
    """One harness in a pseudo-terminal, plus the signals the keeper may use."""

    def __init__(self, harness: str, argv: list[str], cwd: Path, env: dict, run_dir: Path, events: Path):
        self.harness = harness
        self.events_path = events
        self.events: list[dict] = []
        self._offset = 0
        self.started = time.time()
        self.last_output = self.started
        self.output_bytes = 0
        self.exit_status: int | None = None
        self.log = open(run_dir / "terminal.log", "wb")

        master, slave = os.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 40, 120, 0, 0))
        self.pid = os.fork()
        if self.pid == 0:
            os.setsid()
            fcntl.ioctl(slave, termios.TIOCSCTTY, 0)
            for fd in (0, 1, 2):
                os.dup2(slave, fd)
            os.close(master)
            os.close(slave)
            os.chdir(cwd)
            os.execve(argv[0], argv, env)
        os.close(slave)
        self.master = master

    def pump(self, seconds: float = 0.25) -> None:
        """Move terminal bytes to the log, read new events, notice an exit."""
        ready, _, _ = select.select([self.master], [], [], seconds)
        if ready:
            try:
                data = os.read(self.master, 65536)
            except OSError:
                data = b""
            if data:
                self.log.write(data)
                self.log.flush()
                self.last_output = time.time()
                self.output_bytes += len(data)
                # Terminal protocol, not screen reading: some terminal UIs ask where
                # the cursor is at startup and refuse to run without an answer.
                if b"\x1b[6n" in data:
                    os.write(self.master, b"\x1b[1;1R")
        if self.events_path.exists():
            with open(self.events_path) as f:
                f.seek(self._offset)
                for line in f:
                    if line.endswith("\n"):
                        event = json.loads(line)
                        event["event"] = CANONICAL.get(event["event"], event["event"])
                        self.events.append(event)
                        self._offset += len(line.encode())
        if self.exit_status is None:
            pid, status = os.waitpid(self.pid, os.WNOHANG)
            if pid:
                self.exit_status = status

    def type(self, text: str) -> None:
        try:
            os.write(self.master, text.encode())
            time.sleep(0.6)
            os.write(self.master, b"\r")
        except OSError:
            pass  # the harness has gone; the exit is picked up by pump()

    def signal(self, sig: int) -> None:
        try:
            os.killpg(self.pid, sig)
        except ProcessLookupError:
            pass

    def hooks(self) -> list[dict]:
        return [e for e in self.events if e["source"] == "hook"]

    def reports(self) -> list[dict]:
        return [e for e in self.events if e["source"] == "report"]


def derive_state(s: Session, now: float) -> tuple[str, str]:
    """The state and the reason for it. Uses no terminal content."""
    if s.exit_status is not None:
        return "exited", f"exit status {s.exit_status}"
    hooks = s.hooks()
    quiet = now - s.last_output
    if not hooks:
        if quiet > START_STALL_AFTER:
            return "stalled", f"no hook event yet and terminal silent for {quiet:.0f}s"
        return "starting", "no hook event yet"
    last = hooks[-1]
    name, age = last["event"], now - last["ts"]
    payload = last.get("payload") or {}
    if name == "PermissionRequest" and PERMISSION_HOOK_MEANS_PROMPT[s.harness]:
        return "waiting_input", "permission request hook"
    if name == "Notification":
        kind = payload.get("notification_type") or payload.get("message") or "notification"
        if kind == "idle_prompt":
            return "idle", "notification: idle_prompt"
        return "waiting_input", f"notification: {kind}"
    if name in ("Stop", "SessionStart", "SessionEnd"):
        return "idle", f"last event {name}"
    if min(age, quiet) > HUNG_AFTER:
        return "hung", f"last event {name} {age:.0f}s ago, terminal silent for {quiet:.0f}s"
    return "working", f"last event {name}"


# ---------------------------------------------------------------- scenarios

class Run:
    def __init__(self, session: Session, run_dir: Path, accept_trust: bool = False):
        self.s = session
        self.run_dir = run_dir
        self.accept_trust = accept_trust
        self.trust_keys = 0
        self.transitions: list[dict] = []
        self.checks: list[dict] = []
        self.state = ""

    def tick(self) -> str:
        self.s.pump()
        now = time.time()
        # Opt-in workaround for the folder-trust dialog: one blind Enter if nothing has
        # happened 15s after start. It is the only keystroke sent without a signal, and
        # it only makes sense for a workspace the keeper created itself.
        waited = now - self.s.started
        if self.accept_trust and not self.s.hooks() and self.s.exit_status is None:
            if waited > 15 + 20 * self.trust_keys and self.trust_keys < 2:
                self.trust_keys += 1
                print(f"  [{waited:6.1f}s] sent Enter to accept folder trust", flush=True)
                os.write(self.s.master, b"\r")
        state, reason = derive_state(self.s, now)
        if state != self.state:
            self.state = state
            entry = {"seconds": round(now - self.s.started, 1), "state": state, "reason": reason}
            self.transitions.append(entry)
            print(f"  [{entry['seconds']:6.1f}s] {state:<14} {reason}", flush=True)
        return state

    def wait_for(self, what: str, condition, timeout: float) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            self.tick()
            if condition():
                return True
            if self.s.exit_status is not None:
                break
            if self.state == "stalled" and not (self.accept_trust and self.trust_keys < 2):
                break
        print(f"  ! timed out waiting for: {what}", flush=True)
        return False

    def hold(self, seconds: float) -> None:
        deadline = time.time() + seconds
        while time.time() < deadline:
            self.tick()

    def check(self, name: str, passed: bool, detail: str = "") -> None:
        self.checks.append({"check": name, "passed": bool(passed), "detail": detail})
        print(f"  {'PASS' if passed else 'FAIL'}  {name}" + (f" ({detail})" if detail else ""), flush=True)

    def stop(self) -> None:
        if self.s.exit_status is None:
            self.s.signal(signal.SIGCONT)
            self.s.signal(signal.SIGTERM)
            self.wait_for("exit after SIGTERM", lambda: self.s.exit_status is not None, 10)
        if self.s.exit_status is None:
            self.s.signal(signal.SIGKILL)
            self.wait_for("exit after SIGKILL", lambda: self.s.exit_status is not None, 5)
        self.tick()


PROMPTS = {
    "complete": (
        "Create a file named hello.txt containing the single word hi. "
        "Then run this exact shell command: h2h-report done first-task . Then stop."
    ),
    "followup": (
        "Append a second line containing the word again to hello.txt. "
        "Then run this exact shell command: h2h-report done second-task . Then stop."
    ),
    "permission": "Run this exact shell command and nothing else: touch needs-approval.txt",
    "hung": (
        "There is a program named slow-task on the PATH. It takes about a minute and prints nothing. "
        "Run `slow-task` with your shell tool, in the foreground, and wait for it to finish. "
        "Do not run it in the background. Then say done."
    ),
}


def scenario_complete(run: Run, workspace: Path) -> None:
    s = run.s
    reports = lambda n: len(s.reports()) >= n  # noqa: E731
    stops = lambda n: sum(e["event"] == "Stop" for e in s.hooks()) >= n  # noqa: E731

    if not run.wait_for("first turn to finish", lambda: stops(1) and run.state == "idle", 180):
        run.check("first turn finished", False, f"state {run.state}: {run.transitions[-1]['reason']}")
        return
    run.check("turn end is signalled by a hook", stops(1))
    run.check("harness called the reporting tool", reports(1))
    run.check("work was actually done", (workspace / "hello.txt").exists())
    run.check("state is idle after the turn", run.state == "idle", run.state)

    s.type(PROMPTS["followup"])
    prompts = lambda: sum(e["event"] == "UserPromptSubmit" for e in s.hooks())  # noqa: E731
    run.wait_for("typed prompt to be accepted", lambda: prompts() >= 2, 30)
    run.check("a prompt typed into the terminal is accepted", prompts() >= 2)
    run.wait_for("second turn to finish", lambda: stops(2) and run.state == "idle", 180)
    run.check("second turn finished and reported", stops(2) and reports(2))
    text = (workspace / "hello.txt").read_text() if (workspace / "hello.txt").exists() else ""
    run.check("second task was done", "again" in text)

    s.type("/exit")
    exited = run.wait_for("exit after /exit", lambda: s.exit_status is not None, 20)
    run.check("the harness exits on /exit", exited)


def scenario_permission(run: Run, workspace: Path) -> None:
    s = run.s
    started = run.wait_for("the session to start", lambda: bool(s.hooks()), 60)
    if not started:
        run.check("session started", False, f"state {run.state}: {run.transitions[-1]['reason']}")
        return
    asked = run.wait_for("waiting for input", lambda: run.state == "waiting_input", 120)
    reason = run.transitions[-1]["reason"] if run.transitions else ""
    run.check("a permission prompt is detected", asked, reason)
    pre = [e for e in s.hooks() if e["event"] == "PreToolUse"]
    if asked and pre:
        latency = s.started + run.transitions[-1]["seconds"] - pre[-1]["ts"]
        run.check("detected within 10s of the tool call", latency < 10, f"{latency:.1f}s")
    run.hold(12)
    run.check("state stays waiting while unanswered", run.state == "waiting_input", run.state)
    run.check("the action did not run", not (workspace / "needs-approval.txt").exists())


def scenario_hung(run: Run, workspace: Path) -> None:
    s = run.s
    pending = lambda: any(e["event"] == "PreToolUse" for e in s.hooks())  # noqa: E731
    if not run.wait_for("the long command to start", pending, 120):
        run.check("the long command started", False, f"state {run.state}: {run.transitions[-1]['reason']}")
        return
    before = s.output_bytes
    run.hold(12)
    run.check(
        "a long-running command is not mistaken for waiting or hung",
        run.state == "working", f"{run.state}, {s.output_bytes - before} terminal bytes in 12s",
    )
    s.signal(signal.SIGSTOP)
    frozen = run.wait_for("hung", lambda: run.state == "hung", HUNG_AFTER + 15)
    run.check("a frozen harness is detected as hung", frozen, run.transitions[-1]["reason"])
    s.signal(signal.SIGCONT)
    run.hold(4)
    run.check("the state recovers when the harness resumes", run.state == "working", run.state)


SCENARIOS = {"complete": scenario_complete, "permission": scenario_permission, "hung": scenario_hung}


def run(harness: str, scenario: str, kind: str = "subdir", accept_trust: bool = False, user_hooks: bool = False) -> int:
    run_dir = HERE / "runs" / f"{datetime.now():%Y%m%d-%H%M%S}-{harness}-{scenario}"
    run_dir.mkdir(parents=True)
    events = run_dir / "events.jsonl"
    user_hooks = user_hooks and harness == "copilot"
    workspace = make_workspace(harness, events, kind, user_hooks)
    created_folder = install_copilot_user_hooks() if user_hooks else False
    env = clean_env(workspace, events)
    argv = command_for(harness, PROMPTS[scenario], env, allow_work=scenario != "permission", run_dir=run_dir)
    print(f"{harness} / {scenario} / {kind} workspace\n  workspace {workspace}\n  run       {run_dir}", flush=True)

    session = Session(harness, argv, workspace, env, run_dir, events)
    current = Run(session, run_dir, accept_trust)
    try:
        SCENARIOS[scenario](current, workspace)
    finally:
        current.stop()
        current.check("process exit is observed", session.exit_status is not None)
        if user_hooks:
            remove_copilot_user_hooks(created_folder)

    hooks = session.hooks()
    result = {
        "harness": harness,
        "scenario": scenario,
        "workspace_kind": kind,
        "hooks_from": "user folder" if user_hooks else "launch arguments or workspace",
        "trust_keystrokes": current.trust_keys,
        "command": [a if a != PROMPTS[scenario] else "<prompt>" for a in argv],
        "passed": all(c["passed"] for c in current.checks),
        "checks": current.checks,
        "transitions": current.transitions,
        "hook_events_seen": sorted({e["event"] for e in hooks}),
        "hook_sequence": [e["event"] for e in hooks],
        "reports": [{"status": e["event"], "message": e.get("message", "")} for e in session.reports()],
        "seconds": round(time.time() - session.started, 1),
    }
    (run_dir / "result.json").write_text(json.dumps(result, indent=2))
    print(f"  hook events seen: {', '.join(result['hook_events_seen']) or 'none'}")
    print(f"  {'PASSED' if result['passed'] else 'FAILED'} in {result['seconds']}s")
    if kind == "temp":
        shutil.rmtree(workspace, ignore_errors=True)
    elif kind == "worktree":
        subprocess.run(["git", "worktree", "remove", "--force", str(workspace)], cwd=HERE)
    return 0 if result["passed"] else 1


def screen(path: str) -> None:
    """Crude plain-text view of a terminal log, for a human looking into a failed run."""
    data = Path(path).read_bytes().decode(errors="replace")
    data = re.sub(r"\x1b\][^\x07\x1b]*(\x07|\x1b\\)", "", data)      # OSC
    data = re.sub(r"\x1b\[[0-9;?]*[HfJ]", "\n", data)                 # cursor moves, clears
    data = re.sub(r"\x1b\[[0-9;?<>=]*[A-Za-z]", "", data)             # other CSI
    data = re.sub(r"\x1b[()=>][0-9A-Za-z]?", "", data)
    lines = [line.rstrip() for line in data.replace("\r", "\n").split("\n")]
    out: list[str] = []
    for line in lines:
        if line.strip() and (not out or out[-1] != line):
            out.append(line)
    print("\n".join(out[-80:]))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="action", required=True)
    r = sub.add_parser("run")
    r.add_argument("harness", choices=sorted(HOOK_EVENTS))
    r.add_argument("scenario", choices=sorted(SCENARIOS))
    r.add_argument(
        "--workspace", choices=["subdir", "repo", "worktree", "temp"], default="subdir",
        help="how the workspace relates to folders the user already trusts (default: subdir)",
    )
    r.add_argument(
        "--accept-trust", action="store_true",
        help="send one Enter if the harness shows nothing but a folder-trust dialog at start",
    )
    r.add_argument(
        "--user-hooks", action="store_true",
        help="Copilot only: install the hooks in ~/.copilot/hooks for the run instead of in the workspace",
    )
    v = sub.add_parser("screen")
    v.add_argument("log")
    args = parser.parse_args()
    if args.action == "screen":
        screen(args.log)
    else:
        sys.exit(run(args.harness, args.scenario, args.workspace, args.accept_trust, args.user_hooks))


if __name__ == "__main__":
    main()
