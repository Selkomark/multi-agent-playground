"""Hidden acceptance tests for the durations task. No harness ever sees this file.

    python acceptance.py <workspace>      # prints JSON: passed, total, failed case names
"""

import importlib.util
import json
import sys
from pathlib import Path

H, M, S = 3_600_000, 60_000, 1_000
D, W = 24 * H, 7 * 24 * H

PARSE_OK = {
    "1h30m": 90 * M, "2d 4h": 2 * D + 4 * H, "500ms": 500, "1w": W, "1w2d3h4m5s6ms": W + 2 * D + 3 * H + 4 * M + 5 * S + 6,
    "  10s  ": 10 * S, "1H30M": 90 * M, "5MS": 5, "1m 1ms": M + 1, "1.5h": 90 * M, "1h 0.5m": H + 30 * S,
    "0.0005s": 1, "0.0004s": 0, "2.5ms": 3, "-2.5ms": -3, "-1h30m": -90 * M, "-0s": 0, "0": 0, "0s": 0,
    "1m30s": 90 * S, "3ms": 3, "1s500ms": 1500,
}
PARSE_VALUE_ERROR = [
    "", "   ", "30m1h", "1h2h", "1.5h30m", "1 h", "10", "1x", "h", "+1h", "1h-30m", "--1h", "1.h", ".5h",
    "1ms1s", "1m1m", "1h,30m", "- 1h", "1e3s", "-", "0 0",
]
PARSE_TYPE_ERROR = [None, 5, 1.5, b"1h", ["1h"]]
FORMAT_OK = {
    90 * M: "1h30m", W: "1w", 0: "0s", -90 * M: "-1h30m", 1: "1ms", 1500: "1s500ms", W + 1: "1w1ms",
    8 * D: "1w1d", 59 * S + 999: "59s999ms", -1: "-1ms", 25 * H: "1d1h",
}
FORMAT_TYPE_ERROR = [None, "1h", 1.5, True, False]
ROUND_TRIP = [0, 1, -1, 999, 1000, 61_001, 86_399_999, 86_400_000, 604_800_001, -604_799_999, 123_456_789_012]


def main() -> None:
    path = Path(sys.argv[1]) / "durations.py"
    results: dict[str, bool] = {}
    try:
        spec = importlib.util.spec_from_file_location("durations", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        parse, fmt = module.parse_duration, module.format_duration
    except Exception as error:  # noqa: BLE001
        print(json.dumps({"passed": 0, "total": 0, "failed": [f"module did not load: {error!r}"]}))
        return

    def case(name: str, check) -> None:
        try:
            results[name] = bool(check())
        except Exception:  # noqa: BLE001
            results[name] = False

    def raises(kind, call) -> bool:
        try:
            call()
        except kind:
            return True
        except Exception:  # noqa: BLE001
            return False
        return False

    for text, want in PARSE_OK.items():
        case(f"parse {text!r}", lambda: (r := parse(text)) == want and type(r) is int)
    for text in PARSE_VALUE_ERROR:
        case(f"parse {text!r} raises ValueError", lambda: raises(ValueError, lambda: parse(text)))
    for value in PARSE_TYPE_ERROR:
        case(f"parse {value!r} raises TypeError", lambda: raises(TypeError, lambda: parse(value)))
    for value, want in FORMAT_OK.items():
        case(f"format {value}", lambda: fmt(value) == want)
    for value in FORMAT_TYPE_ERROR:
        case(f"format {value!r} raises TypeError", lambda: raises(TypeError, lambda: fmt(value)))
    for value in ROUND_TRIP:
        case(f"round trip {value}", lambda: parse(fmt(value)) == value)

    failed = [name for name, ok in results.items() if not ok]
    print(json.dumps({"passed": len(results) - len(failed), "total": len(results), "failed": failed}))


if __name__ == "__main__":
    main()
