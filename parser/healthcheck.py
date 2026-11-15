"""Fast, read-only checks for every external weekly data source.

Unlike ``parser.run_all``, this module requests only the smallest useful sample,
does not save chart data and does not populate the Twitch weekly cache.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from contextlib import nullcontext
from time import monotonic


EXTRA_CHECKS = ("whatstat", "wordstat")


def _validate_chart_sample(key: str, chart, items: object) -> str:
    if not isinstance(items, list) or not items:
        raise RuntimeError("source returned no positions")
    item = items[0]
    if not isinstance(item, dict):
        raise RuntimeError("the first position is not an object")
    entry = chart.to_entry(item)
    if not isinstance(entry.get("position"), int) or entry["position"] < 1:
        raise RuntimeError("position is missing or invalid")
    if not str(entry.get("title") or "").strip():
        raise RuntimeError("title is missing")
    if not str(entry.get("match_key") or "").strip():
        raise RuntimeError("match_key is missing")
    return f"structure OK, sample: {entry['title']}"


def _check_chart(key: str, chart) -> str:
    if key == "twitch":
        # A single complete channel checks both the ranking and weekly-stat pages,
        # while deliberately bypassing the persistent production cache.
        from parser.twitch import get_russian_twitch_ranking

        items = get_russian_twitch_ranking(1, cache_path=None)
    else:
        items = chart.fetch(1)
    return _validate_chart_sample(key, chart, items)


def _check_whatstat() -> str:
    from parser.whatstat_categories import get_whatstat_categories

    rows = get_whatstat_categories(pages=1)
    first = rows[0]
    required = {"position", "title", "average_viewers", "category_id", "url"}
    if not required.issubset(first):
        raise RuntimeError("category table structure has changed")
    return f"structure OK, {len(rows)} categories on page 1"


def _check_wordstat() -> str:
    from parser.wordstat import get_wordstat_count

    count = get_wordstat_count("В тренде")
    if type(count) is not int or count < 0:
        raise RuntimeError("API returned an invalid count")
    return f"authorization and response structure OK, count: {count}"


def main(argv: list[str] | None = None) -> int:
    # Health checks must not open or reset production circuit breakers.
    temporary = tempfile.TemporaryDirectory(prefix="v-trende-healthcheck-")
    previous_state_file = os.environ.get("CIRCUIT_BREAKER_STATE_FILE")
    os.environ["CIRCUIT_BREAKER_STATE_FILE"] = os.path.join(temporary.name, "circuits.json")

    from parser.common.charts import CHARTS
    from parser.scheduler import _virtual_display

    names = [*CHARTS, *EXTRA_CHECKS]
    cli = argparse.ArgumentParser(description="Fast read-only check of parser sources")
    cli.add_argument("--only", nargs="+", choices=names, help="check selected sources only")
    args = cli.parse_args(argv)
    selected = args.only or names
    failures: list[str] = []

    try:
        display = _virtual_display() if any(name == "zvuk" for name in selected) else nullcontext()
        with display:
            for name in selected:
                started = monotonic()
                try:
                    if name == "whatstat":
                        message = _check_whatstat()
                    elif name == "wordstat":
                        message = _check_wordstat()
                    else:
                        message = _check_chart(name, CHARTS[name])
                except Exception as error:  # noqa: BLE001 - each source must be reported
                    failures.append(name)
                    message = f"{type(error).__name__}: {error}"
                    status = "FAIL"
                else:
                    status = "OK"
                elapsed = monotonic() - started
                print(f"[{status}] {name}: {message} ({elapsed:.1f}s)", flush=True)
    finally:
        if previous_state_file is None:
            os.environ.pop("CIRCUIT_BREAKER_STATE_FILE", None)
        else:
            os.environ["CIRCUIT_BREAKER_STATE_FILE"] = previous_state_file
        temporary.cleanup()

    print(f"Checked: {len(selected)}, failed: {len(failures)}", flush=True)
    if failures:
        print("Failed sources: " + ", ".join(failures), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
