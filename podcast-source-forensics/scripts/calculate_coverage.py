#!/usr/bin/env python3
"""Merge evidence intervals and calculate strict and extended coverage."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Iterable


STRICT = {"fingerprint"}
EXTENDED = {"fingerprint", "structural"}


def parse_time(value: str) -> float:
    value = value.strip()
    if not value:
        raise ValueError("empty timestamp")
    parts = value.split(":")
    if len(parts) not in {2, 3}:
        raise ValueError(f"expected MM:SS or HH:MM:SS, got {value!r}")
    try:
        numbers = [float(part) for part in parts]
    except ValueError as exc:
        raise ValueError(f"invalid timestamp {value!r}") from exc
    if any(number < 0 for number in numbers) or numbers[-1] >= 60:
        raise ValueError(f"invalid timestamp {value!r}")
    if len(numbers) == 2:
        minutes, seconds = numbers
        return minutes * 60 + seconds
    hours, minutes, seconds = numbers
    if minutes >= 60:
        raise ValueError(f"invalid timestamp {value!r}")
    return hours * 3600 + minutes * 60 + seconds


def merge(intervals: Iterable[tuple[float, float]]) -> list[tuple[float, float]]:
    ordered = sorted(intervals)
    merged: list[list[float]] = []
    for start, end in ordered:
        if end <= start:
            raise ValueError(f"interval end must be after start: {start}-{end}")
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    return [(start, end) for start, end in merged]


def seconds(intervals: Iterable[tuple[float, float]]) -> float:
    return sum(end - start for start, end in intervals)


def format_time(value: float) -> str:
    rounded = int(round(value))
    hours, remainder = divmod(rounded, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def percentage(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        raise ValueError("duration denominator must be greater than zero")
    return round(numerator / denominator * 100, 2)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", required=True, help="Evidence CSV")
    parser.add_argument("--effective-duration", required=True, help="MM:SS or HH:MM:SS")
    parser.add_argument("--total-duration", required=True, help="MM:SS or HH:MM:SS")
    parser.add_argument("--output", help="Optional JSON output path")
    args = parser.parse_args()

    try:
        effective = parse_time(args.effective_duration)
        total = parse_time(args.total_duration)
        if effective > total:
            raise ValueError("effective duration cannot exceed total duration")

        evidence_path = Path(args.evidence)
        strict_raw: list[tuple[float, float]] = []
        extended_raw: list[tuple[float, float]] = []
        accepted_rows = 0
        with evidence_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            required = {"podcast_start", "podcast_end", "classification"}
            missing = required.difference(reader.fieldnames or [])
            if missing:
                raise ValueError(f"missing CSV columns: {', '.join(sorted(missing))}")
            for line_number, row in enumerate(reader, start=2):
                classification = (row.get("classification") or "").strip().lower()
                if classification not in EXTENDED:
                    continue
                try:
                    interval = (
                        parse_time(row.get("podcast_start") or ""),
                        parse_time(row.get("podcast_end") or ""),
                    )
                except ValueError as exc:
                    raise ValueError(f"CSV line {line_number}: {exc}") from exc
                if interval[1] > total:
                    raise ValueError(f"CSV line {line_number}: interval exceeds total duration")
                accepted_rows += 1
                extended_raw.append(interval)
                if classification in STRICT:
                    strict_raw.append(interval)

        strict_intervals = merge(strict_raw)
        extended_intervals = merge(extended_raw)
        strict_seconds = seconds(strict_intervals)
        extended_seconds = seconds(extended_intervals)
        result = {
            "effective_duration_seconds": effective,
            "total_duration_seconds": total,
            "accepted_evidence_rows": accepted_rows,
            "strict": {
                "classifications": sorted(STRICT),
                "merged_intervals": strict_intervals,
                "seconds": strict_seconds,
                "duration": format_time(strict_seconds),
                "percent_effective": percentage(strict_seconds, effective),
                "percent_total": percentage(strict_seconds, total),
            },
            "extended": {
                "classifications": sorted(EXTENDED),
                "merged_intervals": extended_intervals,
                "seconds": extended_seconds,
                "duration": format_time(extended_seconds),
                "percent_effective": percentage(extended_seconds, effective),
                "percent_total": percentage(extended_seconds, total),
            },
        }
        if strict_seconds > effective or extended_seconds > effective:
            result["warning"] = (
                "Coverage exceeds effective duration. Recheck interval boundaries or denominator."
            )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    print(rendered)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
