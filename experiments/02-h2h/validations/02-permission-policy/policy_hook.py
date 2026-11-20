"""Permission hook for the policy spike: answers a harness's permission request in code.

Registered on the PermissionRequest hook of Claude Code, Codex CLI and Copilot CLI:

    python policy_hook.py <claude|codex|copilot> <run-dir>      # request payload on stdin

The decision comes from policy.json, first matching rule wins:

    allow      the action runs, no prompt is shown
    deny       the action is refused and the rule's message goes back to the model
    ask_user   (no rule matched) the request is put in a queue for the user and the
               hook waits for the answer; with no answer in time it is refused

Every request and decision is appended to decisions.jsonl in the run directory.
"""

import fnmatch
import json
import sys
import time
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent


def answer(harness: str, behavior: str, message: str = "") -> str:
    decision: dict = {"behavior": behavior}
    if message:
        decision["message"] = message
    if harness in ("claude", "codex"):
        return json.dumps({"hookSpecificOutput": {"hookEventName": "PermissionRequest", "decision": decision}})
    return json.dumps(decision)


def main() -> None:
    harness, run_dir = sys.argv[1], Path(sys.argv[2])
    payload = json.loads(sys.stdin.read() or "{}")
    tool = payload.get("tool_name") or payload.get("toolName") or ""
    tool_input = payload.get("tool_input") or payload.get("toolInput") or {}
    command = tool_input.get("command", "") if isinstance(tool_input, dict) else ""
    subject = command or json.dumps(tool_input)[:200]

    # Keep the keeper's view of the session complete: this hook replaces the plain logger.
    name = "permissionRequest" if harness == "copilot" else "PermissionRequest"
    with open(run_dir / "events.jsonl", "a") as events:
        events.write(json.dumps({"ts": time.time(), "source": "hook", "event": name, "payload": payload}) + "\n")

    policy = json.loads((HERE / "policy.json").read_text())
    record = {"ts": time.time(), "tool": tool, "subject": subject}

    def finish(behavior: str, how: str, message: str = "") -> None:
        record.update(decision=behavior, decided_by=how, message=message, seconds=round(time.time() - record["ts"], 1))
        with open(run_dir / "decisions.jsonl", "a") as log:
            log.write(json.dumps(record) + "\n")
        print(answer(harness, behavior, message))

    for rule in policy["rules"]:
        if command and fnmatch.fnmatch(command.strip(), rule["command"]):
            return finish(rule["decision"], "policy", rule.get("message", ""))

    # No rule: ask the user through the queue and wait.
    request_id = uuid.uuid4().hex[:8]
    (run_dir / "requests").mkdir(exist_ok=True)
    (run_dir / "answers").mkdir(exist_ok=True)
    (run_dir / "requests" / f"{request_id}.json").write_text(json.dumps({"id": request_id, **record}))
    reply = run_dir / "answers" / f"{request_id}.json"
    deadline = time.time() + policy["ask_user_wait_seconds"]
    while time.time() < deadline:
        if reply.exists():
            given = json.loads(reply.read_text())
            return finish("allow" if given["approve"] else "deny", "user", given.get("reason", ""))
        time.sleep(0.25)
    finish("deny", "timeout", "No answer from the user yet. Do not retry; report that this is waiting for approval.")


if __name__ == "__main__":
    main()
