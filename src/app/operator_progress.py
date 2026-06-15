"""Terminal progress reporting for long-running operator commands."""

from __future__ import annotations

from time import perf_counter
import sys


class OperatorProgress:
    """Write progress to stderr without contaminating JSON command output."""

    def __init__(self, *, enabled: bool, label: str) -> None:
        self.enabled = enabled
        self.label = label
        self.is_tty = sys.stderr.isatty()
        self.stage = ""
        self.stage_started = perf_counter()
        self.last_len = 0
        self.last_bucket = -1

    def update(self, stage: str, processed: int, total: int, detail: str = "") -> None:
        if not self.enabled:
            return
        stage_changed = stage != self.stage
        if stage_changed:
            if self.is_tty and self.stage:
                sys.stderr.write("\n")
            self.stage = stage
            self.stage_started = perf_counter()
            self.last_len = 0
            self.last_bucket = -1

        total = max(total, 0)
        processed = max(processed, 0)
        elapsed = max(perf_counter() - self.stage_started, 0.001)
        rate = processed / elapsed if processed else 0.0
        percent = (processed / total * 100) if total else 0.0
        text = f"{self.label}: stage={stage} {processed}/{total}"
        if total:
            text += f" ({percent:5.1f}%)"
        text += f" elapsed={_format_duration(elapsed)}"
        if rate > 0 and total > processed:
            text += f" rate={rate:.2f}/s eta={_format_duration((total - processed) / rate)}"
        if detail:
            text += f" | {detail}"

        if self.is_tty:
            self._write_tty(text)
            return

        bucket = int(percent // 10) if total else 0
        if stage_changed or processed >= total or bucket > self.last_bucket:
            print(text, file=sys.stderr, flush=True)
            self.last_bucket = bucket

    def finish(self, *, status: str, detail: str = "") -> None:
        if not self.enabled:
            return
        if self.is_tty and self.stage:
            sys.stderr.write("\n")
        text = f"{self.label}: status={status}"
        if detail:
            text += f" | {detail}"
        print(text, file=sys.stderr, flush=True)
        self.stage = ""
        self.last_len = 0

    def _write_tty(self, text: str) -> None:
        padding = " " * max(0, self.last_len - len(text))
        sys.stderr.write("\r" + text + padding)
        sys.stderr.flush()
        self.last_len = len(text)


def _format_duration(seconds: float) -> str:
    total_seconds = int(max(seconds, 0))
    minutes, remaining_seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:d}h{minutes:02d}m{remaining_seconds:02d}s"
    if minutes:
        return f"{minutes:d}m{remaining_seconds:02d}s"
    return f"{remaining_seconds:d}s"
