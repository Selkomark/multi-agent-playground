# Task: durations

Create a Python module `durations.py` in this folder with the two functions below. Use only the standard library.

## parse_duration(text) -> int

Parses a duration string and returns the number of milliseconds as an `int`.

- A duration is one or more parts written as `<number><unit>`, for example `1h30m`, `2d 4h` or `500ms`.
- Units: `w` (7 days), `d`, `h`, `m` (minutes), `s`, `ms`. Units are case-insensitive.
- Whitespace is allowed between parts and around the whole string. It is not allowed between a number and its unit.
- Units must appear from largest to smallest, and each unit at most once. `1h30m` is valid. `30m1h` and `1h2h` raise `ValueError`.
- Numbers are non-negative integers. Only the last part may have a decimal fraction: `1.5h` is valid, `1.5h30m` raises `ValueError`. A number must have digits on both sides of a decimal point.
- A result that is not a whole number of milliseconds is rounded to the nearest millisecond, with halves rounded away from zero: `0.0005s` is `1`.
- A leading `-` negates the whole duration: `-1h30m` is `-5400000`. `-0s` is `0`. A `+` sign is not allowed.
- The bare string `0` is valid and means `0`. Any other bare number raises `ValueError`.
- An empty or whitespace-only string raises `ValueError`. Anything that does not match the format raises `ValueError`.
- An argument that is not a `str` raises `TypeError`.

## format_duration(ms) -> str

Formats a number of milliseconds as the canonical duration string.

- Largest units first, parts with a zero value left out, no spaces: `5400000` gives `1h30m`.
- Uses all six units, so `604800000` gives `1w`.
- `0` gives `0s`.
- A negative value gives the string for its absolute value with a leading `-`.
- An argument that is not an `int` raises `TypeError`. A `bool` also raises `TypeError`.
- For every integer `x`, `parse_duration(format_duration(x)) == x`.
