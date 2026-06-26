"""Trend analysis — detect latency degradation before it causes downtime."""

import statistics
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from .db import Database, CheckResult, STATUS_OK, STATUS_WARN, STATUS_DOWN


def analyze_trend(db: Database, target_id: int) -> Dict:
    """Analyze latency trend for a target.

    Returns a dict with:
      - level: "none" | "stable" | "rising" | "spiking" | "degrading"
      - message: human-readable description
      - pct_change: percentage change over the analysis window
      - avg_recent: average latency in last hour
      - avg_baseline: average latency in the 6h before that
    """
    now = datetime.now()

    # Get recent results (last 8h)
    results = db.get_results(target_id, limit=500)
    if not results:
        return {"level": "none", "message": "No data", "pct_change": 0, "avg_recent": None, "avg_baseline": None}

    # Filter to last 8 hours and with latency data
    cutoff = now - timedelta(hours=8)
    points = []
    for r in results:
        if r.latency_ms is not None and r.checked_at and r.checked_at >= cutoff:
            points.append((r.checked_at, r.latency_ms, r.status))

    if len(points) < 5:
        return {"level": "none", "message": "Not enough data", "pct_change": 0, "avg_recent": None, "avg_baseline": None}

    # Split into baseline (6-2h ago) and recent (last 2h)
    two_h_ago = now - timedelta(hours=2)
    six_h_ago = now - timedelta(hours=6)

    baseline = [lat for ts, lat, _ in points if six_h_ago <= ts < two_h_ago]
    recent = [lat for ts, lat, _ in points if ts >= two_h_ago]

    if not recent:
        return {"level": "none", "message": "No recent data", "pct_change": 0, "avg_recent": None, "avg_baseline": None}

    avg_recent = statistics.mean(recent)

    # Count recent failures
    recent_failures = sum(1 for ts, lat, s in points if ts >= two_h_ago and s != STATUS_OK)
    failure_rate = recent_failures / max(len(recent), 1)

    if not baseline:
        # No baseline — just report current
        if failure_rate > 0.3:
            return {
                "level": "spiking",
                "message": "High failure rate: {:.0f}% errors".format(failure_rate * 100),
                "pct_change": 0,
                "avg_recent": round(avg_recent, 1),
                "avg_baseline": None,
            }
        return {
            "level": "stable",
            "message": "Latency: {:.0f}ms avg".format(avg_recent),
            "pct_change": 0,
            "avg_recent": round(avg_recent, 1),
            "avg_baseline": None,
        }

    avg_baseline = statistics.mean(baseline)

    if avg_baseline == 0:
        pct_change = 0
    else:
        pct_change = round(((avg_recent - avg_baseline) / avg_baseline) * 100, 1)

    # Spike detection: recent max is 3x baseline
    recent_max = max(recent)
    if recent_max > avg_baseline * 3 and recent_max > 1000:
        return {
            "level": "spiking",
            "message": "Spike detected: {:.0f}ms peak (baseline {:.0f}ms)".format(recent_max, avg_baseline),
            "pct_change": pct_change,
            "avg_recent": round(avg_recent, 1),
            "avg_baseline": round(avg_baseline, 1),
        }

    # Failure rate check
    if failure_rate > 0.3:
        return {
            "level": "degrading",
            "message": "Degrading: {:.0f}% error rate".format(failure_rate * 100),
            "pct_change": pct_change,
            "avg_recent": round(avg_recent, 1),
            "avg_baseline": round(avg_baseline, 1),
        }

    # Trend detection: latency grew significantly
    if pct_change > 50:
        return {
            "level": "rising",
            "message": "Latency up {}%: {:.0f}ms \u2192 {:.0f}ms".format(
                pct_change, avg_baseline, avg_recent),
            "pct_change": pct_change,
            "avg_recent": round(avg_recent, 1),
            "avg_baseline": round(avg_baseline, 1),
        }

    if pct_change > 25:
        return {
            "level": "rising",
            "message": "Latency creeping up {}%".format(pct_change),
            "pct_change": pct_change,
            "avg_recent": round(avg_recent, 1),
            "avg_baseline": round(avg_baseline, 1),
        }

    return {
        "level": "stable",
        "message": "Stable: {:.0f}ms avg ({}% change)".format(avg_recent, pct_change),
        "pct_change": pct_change,
        "avg_recent": round(avg_recent, 1),
        "avg_baseline": round(avg_baseline, 1),
    }


def should_alert_trend(trend: Dict) -> bool:
    """Should we send an alert based on trend analysis?"""
    return trend.get("level") in ("rising", "spiking", "degrading")


TREND_LEVELS = {
    "none": {"icon": "\u25cb", "color": "#6b7280"},
    "stable": {"icon": "\u25cf", "color": "#22c55e"},
    "rising": {"icon": "\u25b2", "color": "#fbbf24"},
    "spiking": {"icon": "\u26a0", "color": "#f97316"},
    "degrading": {"icon": "\u2716", "color": "#ef4444"},
}
