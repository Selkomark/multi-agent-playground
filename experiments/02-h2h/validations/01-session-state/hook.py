"""Hook target and reporting tool for the session-state spike.

Both append one JSON line to the events file that the keeper tails:

    python hook.py hook   <events-file> <EventName>           # payload on stdin
    python hook.py report <events-file> <status> [message]    # called by the harness

Nothing is printed for hooks, because some harnesses feed hook output back to the model.
"""

import json
import sys
import time


def main() -> None:
    kind, path, name = sys.argv[1], sys.argv[2], sys.argv[3]
    entry: dict = {"ts": time.time(), "source": kind, "event": name}
    if kind == "hook":
        raw = "" if sys.stdin.isatty() else sys.stdin.read()
        try:
            entry["payload"] = json.loads(raw) if raw.strip() else None
        except ValueError:
            entry["payload"] = {"raw": raw[:2000]}
    else:
        entry["message"] = " ".join(sys.argv[4:])
    with open(path, "a") as events:
        events.write(json.dumps(entry) + "\n")
    if kind == "report":
        print(f"recorded: {name}")


if __name__ == "__main__":
    main()
