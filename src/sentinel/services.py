"""Services — formatting helpers, dashboard panel builder."""

from typing import Dict, List, Optional

from rich.align import Align
from rich.panel import Panel
from rich.text import Text

from .db import CheckResult, Target, STATUS_OK, STATUS_WARN, STATUS_DOWN

# ── Status visual mapping ──────────────────────────────────────────────

STATUS_ICONS = {
    STATUS_OK: "\u25cf",      # ●
    STATUS_WARN: "\u25d0",    # ◐
    STATUS_DOWN: "\u2716",    # ✖
    "unknown": "\u25cb",      # ○
}

STATUS_COLORS = {
    STATUS_OK: "#22c55e",
    STATUS_WARN: "#fbbf24",
    STATUS_DOWN: "#ef4444",
    "unknown": "#6b7280",
}

STATUS_EMOJI = {
    STATUS_OK: "\u2705",      # ✅
    STATUS_WARN: "\u26a0\ufe0f",  # ⚠️
    STATUS_DOWN: "\u274c",    # ❌
    "unknown": "\u2753",      # ❓
}

CHECK_TYPE_ICONS = {
    "http": "\U0001f310",    # 🌐
    "ssl": "\U0001f510",     # 🔒
    "dns": "\U0001f4cd",     # 📍
    "port": "\U0001f50c",    # 🔌
    "domain": "\U0001f3e0",  # 🏠
}


def format_latency(ms: Optional[float]) -> str:
    if ms is None:
        return "\u2014"
    if ms < 100:
        return "{:.0f}ms".format(ms)
    if ms < 1000:
        return "{:.0f}ms".format(ms)
    return "{:.1f}s".format(ms / 1000)


def format_latency_colored(ms: Optional[float]) -> Text:
    if ms is None:
        return Text("\u2014", style="dim")
    if ms < 100:
        return Text("{:.0f}ms".format(ms), style="#22c55e")
    if ms < 500:
        return Text("{:.0f}ms".format(ms), style="#fbbf24")
    return Text("{:.0f}ms".format(ms), style="#ef4444")


def format_uptime(pct: float) -> str:
    if pct >= 99.9:
        return "{:.1f}%".format(pct)
    if pct >= 99:
        return "{:.1f}%".format(pct)
    if pct >= 95:
        return "{:.1f}%".format(pct)
    return "{:.1f}%".format(pct)


def format_uptime_colored(pct: float) -> Text:
    if pct >= 99.9:
        return Text("{:.1f}%".format(pct), style="bold #22c55e")
    if pct >= 99:
        return Text("{:.1f}%".format(pct), style="#22c55e")
    if pct >= 95:
        return Text("{:.1f}%".format(pct), style="#fbbf24")
    return Text("{:.1f}%".format(pct), style="#ef4444")


# ── Dashboard panel ────────────────────────────────────────────────────

BAR_COLORS_BY_STATUS = {
    STATUS_OK: "#22c55e",
    STATUS_WARN: "#fbbf24",
    STATUS_DOWN: "#ef4444",
    "unknown": "#6b7280",
}


def make_dashboard_panel(targets, latest, db) -> Panel:
    """Build a rich stats dashboard panel."""
    if not targets:
        return Panel(
            Align.center(Text("No targets yet", style="dim"), vertical="middle"),
            border_style="#0E2F76",
            title="Sentinel",
        )

    lines = Text()

    # Summary counts
    ok_count = 0
    warn_count = 0
    down_count = 0
    for t in targets:
        r = latest.get(t.id)
        if r:
            if r.status == STATUS_OK:
                ok_count += 1
            elif r.status == STATUS_WARN:
                warn_count += 1
            else:
                down_count += 1
        else:
            down_count += 1

    total = len(targets)

    lines.append("  ")
    lines.append("\u25cf ", style="#22c55e")
    lines.append("{} OK".format(ok_count), style="bold #22c55e")
    lines.append("   ")
    if warn_count:
        lines.append("\u25d0 ", style="#fbbf24")
        lines.append("{} WARN".format(warn_count), style="bold #fbbf24")
        lines.append("   ")
    if down_count:
        lines.append("\u2716 ", style="#ef4444")
        lines.append("{} DOWN".format(down_count), style="bold #ef4444")
        lines.append("   ")

    lines.append("\n\n")

    # Per-target status
    for t in targets:
        r = latest.get(t.id)
        icon = CHECK_TYPE_ICONS.get(t.check_type, "?")

        if r:
            s_color = STATUS_COLORS.get(r.status, "#6b7280")
            s_icon = STATUS_ICONS.get(r.status, "\u25cb")

            lines.append("  ")
            lines.append(s_icon, style="bold {}".format(s_color))
            lines.append(" ")
            lines.append(t.name, style="bold")
            lines.append("  ", style="dim")
            lines.append(t.check_type, style="dim")
            lines.append("  ")

            # Latency bar
            if r.latency_ms is not None:
                bar_len = min(int(r.latency_ms / 50), 20)
                bar_len = max(bar_len, 1)
                bar = "\u2588" * bar_len + "\u2591" * (20 - bar_len)
                lines.append(bar, style=s_color)
                lines.append(" ")
                lines.append(format_latency(r.latency_ms), style=s_color)
            else:
                lines.append("\u2591" * 20, style="dim")
                lines.append(" ")
                lines.append("\u2014", style="dim")

            lines.append("   ")
            lines.append(r.message[:35], style="dim")
        else:
            lines.append("  ")
            lines.append("\u25cb ", style="dim")
            lines.append(t.name, style="dim")
            lines.append("  no data", style="dim")

        lines.append("\n")

    # Overall stats
    lines.append("\n")
    lines.append("  Total: {} targets".format(total), style="dim")

    return Panel(lines, border_style="#0E2F76", title="[bold #0E2F76]Sentinel Dashboard[/]", padding=(1, 2))
