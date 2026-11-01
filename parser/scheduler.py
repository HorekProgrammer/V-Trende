"""Команды для системного планировщика еженедельного обновления MVP."""

import argparse
import os
import shutil
import subprocess
import sys
import traceback
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from datetime import datetime
from pathlib import Path
from time import sleep

from parser.common.upload import MOSCOW_TZ

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = PROJECT_ROOT / "data" / "logs"


@contextmanager
def _virtual_display():
    """Provide a display for parsers that must run Chromium in headed mode."""
    if os.name != "posix" or os.environ.get("DISPLAY") or not shutil.which("Xvfb"):
        yield
        return
    display = ":99"
    process = subprocess.Popen(
        ["Xvfb", display, "-screen", "0", "1280x720x24"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        sleep(1)
        os.environ["DISPLAY"] = display
        yield
    finally:
        os.environ.pop("DISPLAY", None)
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()


def _execute(action: str) -> int:
    if action == "prepare":
        from parser.run_all import main

        return main(["--save", "--next-week", "--defer-publish"])

    from parser.publish_rankings import main

    return main()


def main(argv: list[str] | None = None) -> int:
    cli = argparse.ArgumentParser(description="Плановые задания В-Тренде")
    cli.add_argument("action", choices=("prepare", "publish"))
    args = cli.parse_args(argv)

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    moment = datetime.now(MOSCOW_TZ)
    path = LOG_DIR / f"scheduler-{moment:%Y-%m}.log"
    with path.open("a", encoding="utf-8") as log, redirect_stdout(log), redirect_stderr(log):
        print(f"\n[{moment.isoformat(timespec='seconds')}] {args.action}: запуск", flush=True)
        try:
            with _virtual_display():
                code = _execute(args.action)
        except Exception:  # noqa: BLE001 — планировщик обязан оставить причину в журнале
            traceback.print_exc()
            code = 1
        finished = datetime.now(MOSCOW_TZ)
        print(f"[{finished.isoformat(timespec='seconds')}] {args.action}: код {code}", flush=True)
    return code


if __name__ == "__main__":
    sys.exit(main())
