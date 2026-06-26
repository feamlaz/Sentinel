"""Web UI — FastAPI-powered status dashboard."""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from .db import Database, STATUS_OK, STATUS_WARN, STATUS_DOWN
from .checkers import run_all_checks
from .services import (
    STATUS_ICONS, STATUS_COLORS, CHECK_TYPE_ICONS,
    STATUS_EMOJI, format_latency, format_uptime,
)

TEMPLATES_DIR = Path(__file__).parent / "templates"


def _get_latency_history(db, target_id, hours=24):
    """Get latency data points for sparkline chart."""
    results = db.get_results(target_id, limit=200)
    now = datetime.now()
    cutoff = now.timestamp() - (hours * 3600)

    points = []
    for r in reversed(results):  # oldest first
        if r.latency_ms is not None and r.checked_at:
            ts = r.checked_at.timestamp()
            if ts >= cutoff:
                points.append({
                    "latency": r.latency_ms,
                    "status": r.status,
                    "time": r.checked_at.strftime("%H:%M"),
                })
    return points


def _get_trend_info(db, target_id):
    """Get trend analysis for a target."""
    from .trends import analyze_trend
    return analyze_trend(db, target_id)


def create_app(db_path=None):
    app = FastAPI(title="Sentinel", docs_url=None, redoc_url=None)
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
    db = Database(db_path)

    @app.get("/", response_class=HTMLResponse)
    async def dashboard(request: Request):
        targets = db.list_targets()
        latest = db.get_all_latest()

        target_data = []
        ok_count = 0
        warn_count = 0
        down_count = 0

        for t in targets:
            r = latest.get(t.id)
            # Latency history for sparkline
            history = _get_latency_history(db, t.id if t.id else 0, hours=24)
            # Trend analysis
            trend = _get_trend_info(db, t.id if t.id else 0)

            if r:
                s = r.status
                if s == STATUS_OK:
                    ok_count += 1
                elif s == STATUS_WARN:
                    warn_count += 1
                else:
                    down_count += 1

                target_data.append({
                    "id": t.id,
                    "name": t.name,
                    "host": t.host,
                    "port": t.port,
                    "check_type": t.check_type,
                    "type_icon": CHECK_TYPE_ICONS.get(t.check_type, ""),
                    "status": s,
                    "status_icon": STATUS_ICONS.get(s, "\u25cb"),
                    "status_color": STATUS_COLORS.get(s, "#6b7280"),
                    "status_emoji": STATUS_EMOJI.get(s, ""),
                    "latency": format_latency(r.latency_ms),
                    "latency_ms": r.latency_ms,
                    "uptime": format_uptime(db.get_uptime(t.id)),
                    "uptime_pct": db.get_uptime(t.id),
                    "message": r.message,
                    "checked_at": r.checked_at.strftime("%H:%M:%S") if r.checked_at else "\u2014",
                    "details": json.loads(r.details) if r.details else {},
                    "history": history,
                    "trend": trend,
                })
            else:
                down_count += 1
                target_data.append({
                    "id": t.id,
                    "name": t.name,
                    "host": t.host,
                    "port": t.port,
                    "check_type": t.check_type,
                    "type_icon": CHECK_TYPE_ICONS.get(t.check_type, ""),
                    "status": "unknown",
                    "status_icon": "\u25cb",
                    "status_color": "#6b7280",
                    "status_emoji": "\u2753",
                    "latency": "\u2014",
                    "latency_ms": None,
                    "uptime": "\u2014",
                    "uptime_pct": 100.0,
                    "message": "No data yet",
                    "checked_at": "\u2014",
                    "details": {},
                    "history": [],
                    "trend": {"level": "none", "message": "No data"},
                })

        total = len(targets)
        overall = "ok" if ok_count == total and total > 0 else ("warn" if warn_count else "down")

        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "targets": target_data,
            "total": total,
            "ok_count": ok_count,
            "warn_count": warn_count,
            "down_count": down_count,
            "overall": overall,
            "now": datetime.now().strftime("%H:%M:%S"),
        })

    @app.get("/api/check")
    async def api_check():
        results = run_all_checks(db)
        return [
            {"target": t.name, "status": r.status, "message": r.message, "latency_ms": r.latency_ms}
            for t, r in results
        ]

    @app.get("/api/status")
    async def api_status():
        targets = db.list_targets()
        latest = db.get_all_latest()
        data = []
        for t in targets:
            r = latest.get(t.id)
            data.append({
                "id": t.id, "name": t.name, "host": t.host,
                "check_type": t.check_type,
                "status": r.status if r else "unknown",
                "latency_ms": r.latency_ms if r else None,
                "message": r.message if r else "",
                "uptime": db.get_uptime(t.id),
            })
        return data

    @app.get("/api/history/{target_id}")
    async def api_history(target_id: int, hours: int = 24):
        return _get_latency_history(db, target_id, hours)

    @app.get("/api/trend/{target_id}")
    async def api_trend(target_id: int):
        return _get_trend_info(db, target_id)

    @app.on_event("shutdown")
    def shutdown():
        db.close()

    return app
