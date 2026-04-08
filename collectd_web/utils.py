"""Shared constants and helper utilities for collectd-web."""

from __future__ import annotations

# Maps timespan name → seconds (mirrors $ValidTimespan in collection.modified.cgi)
VALID_TIMESPANS: dict[str, int] = {
    "hour": 3_600,
    "day": 86_400,
    "week": 7 * 86_400,
    "month": 31 * 86_400,
    "year": 366 * 86_400,
    "decade": 10 * 366 * 86_400,
}

# Default RRD graph rendering arguments
# (mirrors @RRDDefaultArgs in collection.modified.cgi)
RRD_DEFAULT_ARGS: list[str] = [
    "--rigid",
    "-w", "1040",
    "-h", "360",
    "--alt-autoscale-max",
    "--alt-y-grid",
    "--slope-mode",
    "--font", "TITLE:28:Monospace",
    "--font", "AXIS:10:Monospace",
    "--font", "LEGEND:12:Monospace",
    "--font", "UNIT:12:Monospace",
    "-c", "BACK#EEEEEEFF",
    "-c", "CANVAS#FFFFFF00",
    "-c", "SHADEA#EEEEEEFF",
    "-c", "SHADEB#EEEEEEFF",
    "-i",
]


def timespan_to_seconds(timespan: str) -> int | None:
    """Convert a named timespan to seconds, or None if unrecognised."""
    return VALID_TIMESPANS.get(timespan)
